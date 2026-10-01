import logging
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO)

@dataclass
class Mod:
    mod_id: str
    name: str
    direction: str
    enabled: bool

class ModManager:
    def __init__(self, mods_path: str):
        self.mods_path = mods_path

        self.mods_list: dict[str, Mod]

        self.load_mods()

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
                logging.warning(f"[WARN] Mod <{mod_file.name}> 加载失败: {err}")

    def _load(self, mod_file: Path):
        pass


def get_mod_manager(path: str):
    return ModManager(path)


if __name__ == "__main__":
    mods_dir_path = r"../../mods"

    mod_manager = get_mod_manager(mods_dir_path)


