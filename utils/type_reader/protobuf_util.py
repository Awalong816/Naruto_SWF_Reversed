import json


class ProtobufReader:
    @staticmethod
    def _read_varint(data: bytes, position: int):
        value = 0
        shift = 0

        while position < len(data):
            current = data[position]
            position += 1

            value |= (current & 0x7F) << shift

            if current < 0x80:
                return value, position

            shift += 7

            if shift >= 64:
                raise ValueError("Varint过长")

        raise ValueError("Varint数据不完整")

    def _read_protobuf(self, data: bytes, depth=0):
        position = 0
        fields = []

        while position < len(data):
            key, position = self._read_varint(data, position)

            field_number = key >> 3
            wire_type = key & 0x07

            if field_number == 0:
                raise ValueError("非法Protobuf字段号0")

            item = {
                "field": field_number,
                "wire_type": wire_type,
            }

            # Varint：int、uint、bool、enum等
            if wire_type == 0:
                value, position = self._read_varint(data, position)
                item["value"] = value

            # 64位定长数据：fixed64、double等
            elif wire_type == 1:
                if position + 8 > len(data):
                    raise ValueError("fixed64数据不完整")

                raw = data[position:position + 8]
                position += 8

                item["value"] = int.from_bytes(raw, "little")
                item["hex"] = raw.hex(" ")

            # 字符串、bytes、嵌套message
            elif wire_type == 2:
                length, position = self._read_varint(data, position)
                end = position + length

                if end > len(data):
                    raise ValueError("length-delimited数据不完整")

                raw = data[position:end]
                position = end

                item["length"] = length

                # 优先尝试UTF-8文本
                try:
                    text = raw.decode("utf-8")

                    if text.isprintable():
                        item["value"] = text
                    else:
                        raise UnicodeDecodeError(
                            "utf-8", raw, 0, len(raw), "不可打印字符"
                        )

                except (UnicodeDecodeError, ValueError):
                    # 再尝试作为嵌套Protobuf
                    try:
                        if raw and depth < 5:
                            item["value"] = self._read_protobuf(
                                raw,
                                depth + 1,
                            )
                        else:
                            item["hex"] = raw.hex(" ")

                    except Exception:
                        item["hex"] = raw.hex(" ")

            # 32位定长数据：fixed32、float等
            elif wire_type == 5:
                if position + 4 > len(data):
                    raise ValueError("fixed32数据不完整")

                raw = data[position:position + 4]
                position += 4

                item["value"] = int.from_bytes(raw, "little")
                item["hex"] = raw.hex(" ")

            else:
                raise ValueError(f"暂不支持wire_type={wire_type}")

            fields.append(item)

        return fields

    def read_bytes(self, body: bytes) -> str:
        """
        body必须是：
        1. 已完成TEA解密
        2. 不包含36字节游戏协议头
        """
        result = self._read_protobuf(body)

        return result


def _get_protobuf_reader():
    return ProtobufReader()