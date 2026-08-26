from .amf3_util import _get_amf3_reader


class TypeReaderManager:
    def __init__(self):
        self.readers = {
            "amf3": _get_amf3_reader(),
        }

    def read_bytes(self, _bytes, method):
        reader = self.readers[method]
        return reader.read_bytes(_bytes)


def get_type_reader_manager():
    return TypeReaderManager()