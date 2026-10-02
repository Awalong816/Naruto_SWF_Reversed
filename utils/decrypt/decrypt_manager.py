from pathlib import Path

from .decrypt_game_server_swf import get_naruto_server_decrypt_manager
from .game_data_crypt import get_game_data_crypt_manager

class DecryptManager:
    def __init__(self):
        # 文件解密/混淆 不同文件种类或名称有专门的解法
        self.NarutoServer = get_naruto_server_decrypt_manager()
        # 数据解密 解密tcp通道中传递的数据包为明文
        self.DataCryptServer = get_game_data_crypt_manager()

    def decrypt_file(self, filename: str, debug=False):
        if "NarutoServer" in filename:
            file = Path(filename)
            if file.exists() and file.is_file():
                data = file.read_bytes()
                data = self.NarutoServer.decrypt(data=data)
                file.write_bytes(data)
                if debug:
                    print(f"{filename} 解密替换完成")
            elif debug:
                print(f"没有找到目标文件: {filename}")
        else:
            if debug:
                print(f"非加密文件，略过")

    def decrypt_data(self, data: bytes):
        result = self.DataCryptServer.decrypt(data)
        return result["data"]

    def encrypt_action_spec(self, action_spec: dict):
        pass


def get_decrypt_manger():
    return DecryptManager()