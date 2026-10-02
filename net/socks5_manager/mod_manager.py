import logging
from dataclasses import dataclass
from pathlib import Path
from importlib import util as import_util

logging.basicConfig(level=logging.INFO)

@dataclass
class Scene:
    direction: str
    command_id: int
    time_slot: list[tuple]

@dataclass
class Mod:
    mod_id: str
    name: str
    scene: Scene
    enabled: bool

class ModManager:
    def __init__(self, mods_path: str):
        self.mods_path = mods_path

    def list_mods(self):
        pass

    def load_mods(self):
        mods_dir = Path(self.mods_path)
        print(mods_dir.resolve())
        mods_dir.mkdir(
            parents=True,  # 父目录不存在时，自动一起创建
            exist_ok=True,  # 目录已存在时不报错
        )

        for mod_file in mods_dir.glob("*.py"):
            try:
                self._load(mod_file)
            except Exception as err:
                logging.warning(f"[WARN] Mod <{mod_file.stem}> 加载失败: {err}")

    def _load(self, mod_file: Path):
        """
        自主实现import
        模块的配置(名字，位置)，组装完后直接进入全局引用字典sys.modules，不需要额外导入
        :param mod_file:
        :return:
        """
        # 配置创建
        module_spec = import_util.spec_from_file_location(
            f"naruto_mod_{mod_file.stem}", # 名字加专属标记方便辨识防止跟其他已有依赖重名
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
            {}
        )


def get_mod_manager(path: str):
    return ModManager(path)


if __name__ == "__main__":
    mods_dir_path = r"../../mods"

    mod_manager = get_mod_manager(mods_dir_path)


