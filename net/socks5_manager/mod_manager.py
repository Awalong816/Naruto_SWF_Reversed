import logging
import threading as th
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

    def enabled_init(self):
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

    def start(self):
        ...

    def stop(self):
        ...

# 每个模型的运行状态
class ModRunTime:
    def __init__(self, mod: BaseMod):
        self.mod_name = mod.MOD_INFO["name"]
        self.mod_id = mod.MOD_INFO["id"]
        self.enabled = mod.enabled


class ModManager:
    """
    mod manager负责处理分发数据，获得触发事件、定时事件，不负责判断request_id
    """
    def __init__(self, mods_path: str):
        self.mods_path = mods_path

        self.mod_lock = th.Lock()

        self.mods_lib = {} # 静态注册，保留mod的所有信息
        self.session_mods_state = {}

        # 组件
        self.type_reader = get_type_reader_manager()

    # 注册保存mod
    def log_in_mods(self):
        mods_dir = Path(self.mods_path)

        mods_dir.mkdir(
            parents=True,  # 父目录不存在时，自动一起创建
            exist_ok=True,  # 目录已存在时不报错
        )

        for mod_pack in mods_dir.iterdir():
            if mod_pack.is_dir():
                logging.info(f"[INFO] 正在静态注册Mod <{mod_pack.stem}> 信息...")
                for mod_file in mod_pack.glob("*.py"):
                    try:
                        self._log_in(mod_file)
                        logging.info(f"[INFO] 静态注册Mod <{mod_pack.stem}> 信息成功")
                    except Exception as err:
                        logging.warning(f"[WARN] 静态注册Mod <{mod_file.stem}> 失败: {err}")

    def _log_in(self, mod_file: Path):
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

    def log_in_session(self, session_id):
        # TODO 在mod事件触发和定时触发表里注册静态mod列表的所有方法，并提供可开关的前端接口
        pass


def get_mod_manager(path: str):
    return ModManager(path)


if __name__ == "__main__":
    mods_dir_path = r"../../mods"

    mod_manager = get_mod_manager(mods_dir_path)
    mod_manager.log_in_mods()


