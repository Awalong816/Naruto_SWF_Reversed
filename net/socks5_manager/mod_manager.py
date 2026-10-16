import logging
from dataclasses import dataclass
from pathlib import Path
from importlib import util as import_util

from utils import get_type_reader_manager
from net.socks5_manager.data_packet_manager import DataPack

logging.basicConfig(level=logging.INFO)

class BaseMod:
    def __init__(self):
        self.MOD_INFO: dict
        self.enabled: bool = False

    def enable_init(self):
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


class ModManager:
    """
    mod manager负责处理分发数据，获得触发事件、定时事件，不负责判断request_id
    """
    def __init__(self, mods_path: str):
        self.mods_path = mods_path

        self.mods_lib = {} # 静态注册，保留mod的所有信息
        self.session_event_trigger = {} # 每个会话独立的事件触发状态机 {session_id: {接受条件: 触发函数}}
        self.session_timer_trigger = {} # 每个会话独立的定时任务状态机 {session_id: ...}

        # 组件
        self.type_reader = get_type_reader_manager()

    def list_mods(self, session_id):
        pass

    def load_mods(self):
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
                        self._load(mod_file)
                        logging.info(f"[INFO] 静态注册Mod <{mod_pack.stem}> 信息成功")
                    except Exception as err:
                        logging.warning(f"[WARN] 静态注册Mod <{mod_file.stem}> 失败: {err}")

    def _load(self, mod_file: Path):
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

    # 添加触发事件
    def data_router(self, data_packets: list[DataPack]):
        pass

    # 添加定时事件
    def timer_router(self):
        pass


def get_mod_manager(path: str):
    return ModManager(path)


if __name__ == "__main__":
    mods_dir_path = r"../../mods"

    mod_manager = get_mod_manager(mods_dir_path)
    mod_manager.load_mods()


