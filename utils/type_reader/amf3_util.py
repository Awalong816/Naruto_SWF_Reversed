from pyamf.amf3 import ByteArray


class AMF3Reader:
    def __init__(self):
        pass

    def _get_amf3_part(self, _bytes):
        amf_len = int.from_bytes(_bytes[:4], byteorder='big', signed=False)

        amf_start = 4 # 来源entry: readUnsignedInt() 32位=4字节
        amf_end = amf_start + amf_len # 第 5[4] 位的标记也属于amf的正文内容

        return _bytes[amf_start:amf_end]

    def read_bytes(self, _bytes):
        amf3_part = self._get_amf3_part(_bytes)
        from_array = ByteArray(amf3_part)
        result = from_array.readObject() # tuple(dict)

        # 当前 Py3AMF 的 Dictionary 可能返回：
        # (dictionary, weak_keys)
        if (
                isinstance(result, tuple)
                and len(result) == 2
                and isinstance(result[0], dict)
        ):
            result = result[0]

        return result


def _get_amf3_reader():
    return AMF3Reader()