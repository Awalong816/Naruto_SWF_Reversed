from pathlib import Path

from .decrypt_game_server_swf import get_naruto_server_decrypt_manager

class DecryptManager:
    def __init__(self):
        self.NarutoServer = get_naruto_server_decrypt_manager()

    def decrypt(self, data: bytes, method: str):
        if method == "NarutoServer":
            return self.NarutoServer.decrypt(data=data)
        else:
            return data

    def decrypt_file(self, filename: str, debug=False):
        if "NarutoServer" in filename:
            file = Path(filename)
            if file.exists() and file.is_file():
                data = file.read_bytes()
                data = self.decrypt(data=data, method="NarutoServer")
                file.write_bytes(data)
                if debug:
                    print(f"{filename} 解密替换完成")
            elif debug:
                print(f"没有找到目标文件: {filename}")
        else:
            if debug:
                print(f"非加密文件，略过")

def get_decrypt_manger():
    return DecryptManager()