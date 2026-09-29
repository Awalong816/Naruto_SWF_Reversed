from pathlib import Path

from config.config import Configs

class ModManager:
    def __init__(self, cfg: Configs):
        self.mods_path = cfg.mods_path

    def _list_mods(self):
        pass

    def _load_mods(self):
        mods_dir = Path(self.mods_path)


if __name__ == "__main__":
    pass