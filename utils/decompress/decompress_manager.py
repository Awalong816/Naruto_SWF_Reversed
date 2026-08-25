from lzma_util import _get_lzma_manager


class DecompressManager:
    def __init__(self):
        self.utils = {
            "lzma": _get_lzma_manager,
        }

    def decompress_bytes(self, data):
        decompressed_data = b""
        decompress_type = ""
        for key, client in self.utils.items():
            try:
                decompressed_data = client.decompress_bytes(data)
                decompress_type = key
            except Exception as err:
                continue

        return decompressed_data, decompress_type


def get_decompress_manager():
    return DecompressManager()