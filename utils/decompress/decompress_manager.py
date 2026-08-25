from .lzma_util import _get_lzma_manager


class DecompressManager:
    def __init__(self):
        # 调用函数获取实例
        self.utils = {
            "lzma": _get_lzma_manager(),
        }

    def decompress_bytes(self, data):
        decompressed_data = b""
        decompress_type = ""
        for key, client in self.utils.items():
            try:
                decompressed_data = client.decompress_bytes(data)  # ✅ client 是 LZMAManager 实例
                decompress_type = key
                break  # 解压成功就退出循环
            except Exception as err:
                continue

        return decompressed_data, decompress_type

def get_decompress_manager():
    return DecompressManager()