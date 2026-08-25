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


def test_lzma_manager():
    lzma_manager = _get_lzma_manager()
    test_path = r"/essence_resource/resource.cfg"
    decompressed_data = lzma_manager.decompress_file(test_path)
    return decompressed_data


if __name__ == "__main__":
    print(test_lzma_manager()[:50].hex(" "))
