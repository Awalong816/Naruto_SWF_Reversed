import lzma
from pathlib import Path


class LZMAManager:
    def __init__(self):
        pass

    def decompress_bytes(self, origin_bytes):
        return lzma.decompress(origin_bytes)

    def decompress_file(self, file_path: str):
        """
        解压lzma文件内容，返回解压后的字节
        """
        file_path = Path(file_path)

        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"lzma文件路径不存在或无效: {file_path}")

        origin_data = file_path.read_bytes()
        decompressed_data = lzma.decompress(origin_data)

        return decompressed_data


def _get_lzma_manager():
    return LZMAManager()


def test_lzma_manager(test_path):
    lzma_manager = _get_lzma_manager()
    decompressed_data = lzma_manager.decompress_file(test_path)
    return decompressed_data


if __name__ == "__main__":
    test_path = r"E:\pythonProject\启动器\essence_resource\flash\core\naruto.include.swf"
    lzma_data = test_lzma_manager(test_path)
    test_path = Path(test_path)
    test_path.write_bytes(lzma_data)
    print(f"解压重写入完成")
