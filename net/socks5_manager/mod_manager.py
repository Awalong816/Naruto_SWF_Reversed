import logging
import queue
import json
import threading as th
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from importlib import util as import_util

from utils import get_type_reader_manager
from net.socks5_manager.data_packet_manager import DataPack

logging.basicConfig(level=logging.INFO)

class BaseMod:
    # 静态
    MOD_INFO: dict = {}

    def __init__(self):
        # 可变
        self.enabled: bool = False

    def _enabled_init(self, now=None, **kwargs) -> list[dict]:
        """
        mod在启用时开始需要发送的动作，可以为空
        :return:
        """
        ...

    def is_enabled(self):
        """
        状态机函数
        :return:
        """
        ...

    def event_trigger(self, data_packet: bytes):
        """
        触发事件，非必要
        :param data_packet:
        :return:
        """
        ...

    def timer_trigger(self):
        """
        定时事件，非必要
        :return:
        """
        ...

    def start(self, now=None, **kwargs):
        ...

    def stop(self, now=None, **kwargs):
        ...


# 每个模型的运行状态
class ModRunTime:
    def __init__(self, mod: BaseMod):
        # 本体
        self.instance = mod
        # 运行日志
        self.running_log = []

    # 状态取每一刻的同步状态=指针，否则加入类成员就是某一时刻的静止快照
    def is_enabled(self):
        return self.instance.enabled


class ModManager:
    """
    mod manager负责处理分发数据，获得触发事件、定时事件，不负责判断request_id
    """
    def __init__(self, mods_path: str):
        self.mods_path = mods_path

        self.mod_lock = th.Lock()

        self.mods_lib = {} # 静态注册，保留mod的所有信息
        self.session_mods_state: dict[str, dict[str, ModRunTime]] = {}
        # mod产生的所有动作方向都应该是发送给服务器
        self.session_extra_queue: dict[str, queue.Queue] = {} # 额外动作队列字典，因为不是所有动作都由已知session_id的data_packet发送，比如enabled_init,定时触发事件

        # 组件
        self.type_reader = get_type_reader_manager()

    # 注册保存mod
    def log_in_mods(self):
        mods_dir = Path(self.mods_path)

        mods_dir.mkdir(
            parents=True,  # 父目录不存在时，自动一起创建
            exist_ok=True,  # 目录已存在时不报错
        )

        logging.info(f"开始注册mod依赖...")
        for mod_pack in mods_dir.iterdir():
            if mod_pack.is_dir():
                for mod_file in mod_pack.glob("*.py"):
                    try:
                        self._log_in_mod(mod_file)
                        logging.info(f"  注册Mod <{mod_pack.stem}> 依赖成功")
                    except Exception as err:
                        logging.warning(f"  注册Mod <{mod_file.stem}> 依赖失败: {err}")

    def _log_in_mod(self, mod_file: Path):
        """
        自主实现import
        模块的配置(名字，位置)，组装完后直接进入全局引用字典sys.modules，不需要额外导入
        :param mod_file:
        :return:
        """
        # 配置创建
        module_spec = import_util.spec_from_file_location(
            f"naruto_mod_{mod_file.stem}", # 名字加专属标记方便辨识防止跟其他已有依赖重名,这里作为定义域=from (x) import ...
            mod_file
        )
        if module_spec is None or module_spec.loader is None:
            raise ImportError(
                f"模块创建发生错误=loader"
            )
        # 模块本体创建
        module = import_util.module_from_spec(module_spec) # 给与一个空间实例，并没有启动组装
        # 开始组装,按照spec的方法组装到module空间上，导入完成
        module_spec.loader.exec_module(module)

        # 获得mod的信息
        mod_info = getattr( # 寻找变量属性的get方法
            module,
            "MOD_INFO",
            {},
        )

        mod_id = mod_info.get("id")
        if not mod_id:
            raise ValueError(f"MOD_INFO 缺失属性`id`")

        # 获得业务类
        mod_cls = getattr(
            module,
            "SERVER_MOD_CLASS",
        )

        required_methods = ("start", "stop", "is_enabled")
        for method in required_methods:
            if not callable(getattr(mod_cls, method, None)):
                raise TypeError(f"SERVER_MOD_CLASS 缺少必要方法{method}")

        # 注册进mod表
        if mod_id not in self.mods_lib.keys():
            self.mods_lib[mod_id] = mod_cls

    @staticmethod
    def _get_now():
        now = datetime.now()
        return now

    def log_in_session(self, session_id):
        with self.mod_lock:
            if session_id not in self.session_mods_state:
                id_runtimes = {}
                for mod_id, mod_cls in self.mods_lib.items():
                    instance = mod_cls()
                    try:
                        id_runtimes[mod_id] = ModRunTime(mod=instance)
                    except Exception as err:
                        logging.warning(f"会话 {session_id} 添加mod实例失败: {err}")
                # 先构造好，再一次性登记，消除空表窗口
                self.session_mods_state[session_id] = id_runtimes
                self.session_extra_queue[session_id] = queue.Queue()
                logging.info(f"会话 {session_id} 添加mod完成")
                print(f"会话 {session_id} 状态机:\n{self.session_mods_state}")

    def log_off_session(self, session_id):
        with self.mod_lock:
            runtimes = self.session_mods_state.pop(session_id, None)  # 先摘表
            self.session_extra_queue.pop(session_id, None)  # 先摘队
        if runtimes is None:
            logging.warning(f"没有找到会话 {session_id} 注册mod状态机")
            return
        for mod_id, mod_runtime in runtimes.items():  # 锁外停
            try:
                mod_runtime.instance.stop()
            except Exception as err:
                logging.warning(f"会话 {session_id} 关闭mod {mod_id} 失败: {err}")

    # ======================== 业务方法 ======================
    def list_session_mod_state(self, session_id):
        session_mod_map = {}
        with self.mod_lock:
            session_mods = self.session_mods_state.get(session_id) or {}
            for mod_id, mod_runtime in session_mods.items():
                session_mod_map[mod_id] = {
                    "enabled": mod_runtime.is_enabled(),
                    "info": dict(mod_runtime.instance.MOD_INFO),
                    "running_log": list(mod_runtime.running_log),
                }
        return session_mod_map

    def start_mod_in_session(self, session_id, mod_id):
        try:
            now = self._get_now()
            session_table = self.session_mods_state[session_id]
            mod_instance = session_table[mod_id].instance
            result = mod_instance.start(now=now)
            session_table[mod_id].running_log.append(f"{now.strftime('%Y-%m-%d %H:%M:%S')}:\n<{self.session_mods_state[session_id][mod_id].instance.MOD_INFO.get('name')}> 开始运行")
            # TODO 读动作内容和二进制格式压缩成body加头打包成DataPack发送给服务器
            print(f"action result: {result}")
        except Exception as err:
            raise err

    def stop_mod_in_session(self, session_id, mod_id):
        try:
            now = self._get_now()
            session_table = self.session_mods_state[session_id]
            mod_instance = session_table[mod_id].instance
            mod_instance.stop()
            session_table[session_id][mod_id].running_log.append(f"{now.strftime('%Y-%m-%d %H:%M:%S')}:\n<{self.session_mods_state[session_id][mod_id].instance.MOD_INFO.get('name')}> 停止运行")
        except Exception as err:
            raise err

    def event_trigger(self, session_id, data_packets: list[DataPack]):
        pass

    def timer_trigger(self, session_id):
        pass


def get_mod_manager(path: str):
    return ModManager(path)


if __name__ == "__main__":
    mods_dir_path = r"../../mods"

    mod_manager = get_mod_manager(mods_dir_path)
    mod_manager.log_in_mods()


