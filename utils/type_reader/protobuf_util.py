import json
import struct


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

    @staticmethod
    def _encode_varint(value: int) -> bytes:
        # 负数按64位补码编码，和protobuf的int32/int64一致
        if value < 0:
            value += 1 << 64

        buffer = bytearray()

        while True:
            chunk = value & 0x7F
            value >>= 7

            if value:
                buffer.append(chunk | 0x80)
            else:
                buffer.append(chunk)
                return bytes(buffer)

    def _encode_field(self, field_number: int, value, depth: int) -> bytes:
        # bool 是 int 的子类，必须先判断
        if isinstance(value, bool):
            return (
                self._encode_varint((field_number << 3) | 0)
                + self._encode_varint(int(value))
            )

        if isinstance(value, int):
            return (
                self._encode_varint((field_number << 3) | 0)
                + self._encode_varint(value)
            )

        if isinstance(value, float):
            # double 按 fixed64 编码
            return (
                self._encode_varint((field_number << 3) | 1)
                + struct.pack("<d", value)
            )

        if isinstance(value, str):
            payload = value.encode("utf-8")
        elif isinstance(value, (bytes, bytearray)):
            payload = bytes(value)
        elif isinstance(value, dict):
            payload = self._reverse_protobuf(value, depth + 1)
        else:
            raise TypeError(f"不支持的字段值类型: {type(value)!r}")

        return (
            self._encode_varint((field_number << 3) | 2)
            + self._encode_varint(len(payload))
            + payload
        )

    @staticmethod
    def _reverse_fixed(item: dict, size: int) -> bytes:
        value = item.get("value")

        if isinstance(value, int) and not isinstance(value, bool):
            try:
                return value.to_bytes(size, "little", signed=False)
            except OverflowError:
                raise ValueError(
                    f"fixed{size * 8}数值超出范围: {value}"
                )

        hex_text = item.get("hex")

        if hex_text:
            raw = bytes.fromhex(hex_text.replace(" ", ""))

            if len(raw) != size:
                raise ValueError(
                    f"fixed{size * 8}长度异常: {len(raw)}"
                )

            return raw

        raise ValueError(f"fixed{size * 8}缺少value/hex")

    def _reverse_length_delimited(self, item: dict, depth: int) -> bytes:
        value = item.get("value")

        if isinstance(value, str):
            return value.encode("utf-8")

        if isinstance(value, (bytes, bytearray)):
            return bytes(value)

        if isinstance(value, list):
            return self._reverse_protobuf(value, depth + 1)

        hex_text = item.get("hex")

        if hex_text is not None:
            return bytes.fromhex(hex_text.replace(" ", ""))

        raise ValueError("length-delimited字段缺少value/hex")

    def _reverse_field_table(self, fields: list, depth: int) -> bytes:
        """
        _read_protobuf() 产出的字段表 -> 二进制。
        """
        buffer = bytearray()

        for item in fields:
            if (
                not isinstance(item, dict)
                or "field" not in item
                or "wire_type" not in item
            ):
                raise TypeError(f"字段表元素格式错误: {item!r}")

            field_number = item["field"]
            wire_type = item["wire_type"]

            if isinstance(field_number, bool) or not isinstance(field_number, int):
                raise TypeError(f"字段号必须是int: {field_number!r}")

            if field_number <= 0 or field_number > 0x1FFFFFFF:
                raise ValueError(f"Protobuf字段号超出范围: {field_number}")

            if wire_type not in (0, 1, 2, 5):
                raise ValueError(f"暂不支持wire_type={wire_type}")

            buffer += self._encode_varint(
                (field_number << 3) | wire_type
            )

            if wire_type == 0:
                value = item.get("value", 0)

                if isinstance(value, bool):
                    value = int(value)

                if not isinstance(value, int):
                    raise ValueError(
                        f"varint字段缺少整数value: {item!r}"
                    )

                buffer += self._encode_varint(value)

            elif wire_type == 1:
                buffer += self._reverse_fixed(item, 8)

            elif wire_type == 2:
                payload = self._reverse_length_delimited(item, depth)
                buffer += self._encode_varint(len(payload))
                buffer += payload

            else:
                buffer += self._reverse_fixed(item, 4)

        return bytes(buffer)

    def _reverse_dict(self, data: dict, depth: int) -> bytes:
        buffer = bytearray()

        for field_number, value in data.items():
            if isinstance(field_number, bool) or not isinstance(field_number, int):
                raise TypeError(f"字段号必须是int: {field_number!r}")

            if field_number <= 0 or field_number > 0x1FFFFFFF:
                raise ValueError(f"Protobuf字段号超出范围: {field_number}")

            values = value if isinstance(value, list) else [value]

            for item in values:
                if item is None:
                    continue

                buffer += self._encode_field(
                    field_number,
                    item,
                    depth,
                )

        return bytes(buffer)

    def _reverse_protobuf(self, data, depth: int = 0) -> bytes:
        """
        dict -> protobuf 二进制，只做语法层，不做字段名映射。
        支持两种入参：
            1. dict：键是字段号(int)，值是字段值
               int / bool  -> varint
               float       -> double(fixed64)
               str         -> UTF-8 字符串
               bytes       -> 原始字节
               dict        -> 嵌套 message
               list        -> repeated，每个元素用同一字段号重复编码
               None        -> 跳过，等同字段缺席
            2. list：_read_protobuf() 产出的字段表，
               wire_type 直接来自表项，可字节级还原原始数据
        """
        if depth > 5:
            raise ValueError("Protobuf嵌套层级过深")

        if isinstance(data, dict):
            return self._reverse_dict(data, depth)

        if isinstance(data, list):
            return self._reverse_field_table(data, depth)

        raise TypeError(
            "_reverse_protobuf 只接受 dict 或 _read_protobuf 产出的字段表list"
        )

    def read_bytes(self, body: bytes) -> str:
        """
        body必须是：
        1. 已完成TEA解密
        2. 不包含36字节游戏协议头
        """
        result = self._read_protobuf(body)

        return result

    def reverse_body(self, body):
        """
        body必须是
        1. 符合结构的dict | list[dict]
        :param body:
        :return:
        """
        result = self._reverse_protobuf(body)

        return result


def _get_protobuf_reader():
    return ProtobufReader()

