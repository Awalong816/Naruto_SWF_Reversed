import secrets
import struct


class CryptGameDataManager:
    MAGIC = b"\x09\x01"
    HEADER_SIZE = 36

    TEA_KEY = b"d796c2542916b456"
    TEA_DELTA = 0x9E3779B9
    UINT32_MASK = 0xFFFFFFFF

    def __init__(self):
        self.protocol_state = {
            "uin": None,
            "role_id": None,
            "server_id": None,
        }

        # Mod主动请求使用的ID区间
        self.next_request_id = 0x80000000

        # 记录主动请求，后面匹配响应
        self.pending_requests = {}

    def decrypt(self, data: bytes):
        """
        完整游戏数据包 -> 解析结果字典。
        data需要包含36字节协议头。
        """
        if len(data) < self.HEADER_SIZE:
            raise ValueError("游戏数据包长度不足36字节")

        if data[:2] != self.MAGIC:
            raise ValueError(
                f"游戏数据包magic错误: {data[:2]!r}"
            )

        body_length = int.from_bytes(
            data[2:4],
            "big",
        )

        total_length = self.HEADER_SIZE + body_length

        if len(data) != total_length:
            raise ValueError(
                f"数据包长度异常，"
                f"预期{total_length}，实际{len(data)}"
            )

        encrypted_body = data[self.HEADER_SIZE:]
        plain_body = self._qq_tea_decrypt(
            encrypted_body
        )
        all_data = bytes(data[:self.HEADER_SIZE]) + plain_body

        result = {
            "command_id": int.from_bytes(
                data[4:8],
                "big",
            ),
            "request_id": int.from_bytes(
                data[8:12],
                "big",
            ),
            "message_type": int.from_bytes(
                data[12:16],
                "big",
            ),
            "timeout": struct.unpack(
                "!d",
                data[16:24],
            )[0],
            "uin": int.from_bytes(
                data[24:28],
                "big",
            ),
            "role_id": int.from_bytes(
                data[28:30],
                "big",
            ),
            "server_id": int.from_bytes(
                data[30:32],
                "big",
            ),
            "client_ip": int.from_bytes(
                data[32:36],
                "big",
            ),
            "body_length": body_length,
            "encrypted_body": encrypted_body,
            "body": plain_body,
            "all_data": all_data,
        }

        self.protocol_state["uin"] = result["uin"]
        self.protocol_state["role_id"] = result["role_id"]
        self.protocol_state["server_id"] = result["server_id"]

        return result

    def encrypt(self, action_spec: dict):
        """
        动作字典 -> 带有完整data的动作字典。

        action_spec最低要求：
        {
            "command_id": 198935,
            "body": b"",
        }
        """
        command_id = int(
            action_spec["command_id"]
        )

        plain_body = action_spec.get(
            "body",
            b"",
        )

        if not isinstance(
            plain_body,
            (bytes, bytearray),
        ):
            raise TypeError("body必须是bytes或bytearray")

        uin = action_spec.get(
            "uin",
            self.protocol_state["uin"],
        )
        role_id = action_spec.get(
            "role_id",
            self.protocol_state["role_id"],
        )
        server_id = action_spec.get(
            "server_id",
            self.protocol_state["server_id"],
        )

        if None in (uin, role_id, server_id):
            raise RuntimeError(
                "尚未从游戏数据包中获得"
                "uin、role_id和server_id"
            )

        request_id = action_spec.get(
            "request_id"
        )

        if request_id is None:
            request_id = (
                self._allocate_request_id()
            )

        encrypted_body = self._qq_tea_encrypt(
            bytes(plain_body)
        )

        header = struct.pack(
            "!HHIIIdIHHI",

            0x0901,
            len(encrypted_body),
            command_id,
            request_id,
            1,          # 客户端请求
            0.0,        # timeout
            int(uin),
            int(role_id),
            int(server_id),
            0,          # client_ip
        )

        result = dict(action_spec)

        result.update({
            "request_id": request_id,
            "uin": int(uin),
            "role_id": int(role_id),
            "server_id": int(server_id),
            "body": bytes(plain_body),
            "encrypted_body": encrypted_body,
            "data": header + encrypted_body,
        })

        self.pending_requests[request_id] = {
            "command_id": command_id,
            "source_mod_id": action_spec.get(
                "source_mod_id"
            ),
            "consume_response": action_spec.get(
                "consume_response",
                False,
            ),
        }

        return result

    def _allocate_request_id(self):
        request_id = self.next_request_id

        self.next_request_id = (
            self.next_request_id + 1
        ) & self.UINT32_MASK

        return request_id

    def _qq_tea_encrypt(self, data: bytes):
        key = self.TEA_KEY

        if len(key) != 16:
            raise ValueError("QQ TEA密钥必须为16字节")

        # 1字节头 + padding + 2字节salt
        # + 原文 + 7字节结尾零
        padding_length = (
            8 - ((len(data) + 10) % 8)
        ) % 8

        random_head = secrets.randbelow(256)

        plain = (
            bytes([
                (random_head & 0xF8)
                | padding_length
            ])
            + secrets.token_bytes(
                padding_length
            )
            + secrets.token_bytes(2)
            + data
            + b"\x00" * 7
        )

        previous_x = b"\x00" * 8
        previous_cipher = b"\x00" * 8
        result = bytearray()

        for position in range(
            0,
            len(plain),
            8,
        ):
            block = plain[
                position:position + 8
            ]

            current_x = self._xor_block(
                block,
                previous_cipher,
            )

            encrypted = self._tea_encrypt_block(
                current_x,
                key,
            )

            current_cipher = self._xor_block(
                encrypted,
                previous_x,
            )

            result.extend(current_cipher)

            previous_x = current_x
            previous_cipher = current_cipher

        return bytes(result)

    def _qq_tea_decrypt(self, data: bytes):
        key = self.TEA_KEY

        if len(key) != 16:
            raise ValueError("QQ TEA密钥必须为16字节")

        if len(data) < 16 or len(data) % 8 != 0:
            raise ValueError(
                "QQ TEA密文长度必须至少16字节，"
                "并且是8的倍数"
            )

        previous_x = b"\x00" * 8
        previous_cipher = b"\x00" * 8
        plain = bytearray()

        for position in range(
            0,
            len(data),
            8,
        ):
            current_cipher = data[
                position:position + 8
            ]

            encrypted = self._xor_block(
                current_cipher,
                previous_x,
            )

            current_x = self._tea_decrypt_block(
                encrypted,
                key,
            )

            current_plain = self._xor_block(
                current_x,
                previous_cipher,
            )

            plain.extend(current_plain)

            previous_x = current_x
            previous_cipher = current_cipher

        padding_length = plain[0] & 0x07
        body_start = 1 + padding_length + 2
        body_end = len(plain) - 7

        if body_start > body_end:
            raise ValueError("QQ TEA填充结构异常")

        if plain[body_end:] != b"\x00" * 7:
            raise ValueError(
                "QQ TEA解密失败：结尾校验不通过"
            )

        return bytes(
            plain[body_start:body_end]
        )

    def _tea_encrypt_block(
        self,
        block: bytes,
        key: bytes,
    ):
        value_0, value_1 = struct.unpack(
            "!2I",
            block,
        )
        keys = struct.unpack("!4I", key)

        total = 0

        for _ in range(16):
            total = (
                total + self.TEA_DELTA
            ) & self.UINT32_MASK

            mix = (
                (
                    ((value_1 << 4)
                     & self.UINT32_MASK)
                    + keys[0]
                )
                ^ (
                    value_1 + total
                )
                ^ (
                    (value_1 >> 5)
                    + keys[1]
                )
            )

            value_0 = (
                value_0 + mix
            ) & self.UINT32_MASK

            mix = (
                (
                    ((value_0 << 4)
                     & self.UINT32_MASK)
                    + keys[2]
                )
                ^ (
                    value_0 + total
                )
                ^ (
                    (value_0 >> 5)
                    + keys[3]
                )
            )

            value_1 = (
                value_1 + mix
            ) & self.UINT32_MASK

        return struct.pack(
            "!2I",
            value_0,
            value_1,
        )

    def _tea_decrypt_block(
        self,
        block: bytes,
        key: bytes,
    ):
        value_0, value_1 = struct.unpack(
            "!2I",
            block,
        )
        keys = struct.unpack("!4I", key)

        total = (
            self.TEA_DELTA << 4
        ) & self.UINT32_MASK

        for _ in range(16):
            mix = (
                (
                    ((value_0 << 4)
                     & self.UINT32_MASK)
                    + keys[2]
                )
                ^ (
                    value_0 + total
                )
                ^ (
                    (value_0 >> 5)
                    + keys[3]
                )
            )

            value_1 = (
                value_1 - mix
            ) & self.UINT32_MASK

            mix = (
                (
                    ((value_1 << 4)
                     & self.UINT32_MASK)
                    + keys[0]
                )
                ^ (
                    value_1 + total
                )
                ^ (
                    (value_1 >> 5)
                    + keys[1]
                )
            )

            value_0 = (
                value_0 - mix
            ) & self.UINT32_MASK

            total = (
                total - self.TEA_DELTA
            ) & self.UINT32_MASK

        return struct.pack(
            "!2I",
            value_0,
            value_1,
        )

    @staticmethod
    def _xor_block(
        left: bytes,
        right: bytes,
    ):
        return bytes(
            value_a ^ value_b
            for value_a, value_b
            in zip(left, right)
        )


def get_game_data_crypt_manager():
    return CryptGameDataManager()


if __name__ == "__main__":
    import json

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

    def _read_protobuf(data: bytes, depth=0):
        position = 0
        fields = []

        while position < len(data):
            key, position = _read_varint(data, position)

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
                value, position = _read_varint(data, position)
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
                length, position = _read_varint(data, position)
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
                            item["value"] = _read_protobuf(
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


    def protobuf_to_readable(body: bytes) -> str:
        """
        body必须是：
        1. 已完成TEA解密
        2. 不包含36字节游戏协议头
        """
        result = _read_protobuf(body)

        return json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )

    server = CryptGameDataManager()
    # 198935
    test_data = \
        b'\t\x01\x01\xe0\x00\x03\t\x17\x00\x00\x07$\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x001\xf13\xa6\x00\x00\x02\x1d\x00\x00\x00\x00\n\x0b\x08\x00\x12\x07success\x12S\nM\n\n\x08\xe6\xc4\xaa9\x10\x00\x18\xfb\x03\x12\x0c\xe5\xbf\x98\xe5\xb7\x9d\xe6\xb2\xb3\xe7\xa5\x9e\x18o \xc9\xae\xe2\x04(\xc9\xae\xe2\x042\x18\x08\x01\x10\x00\x18\x00 \x00(\x010\x008\x00@\x00H\x07P\x00X\x00`\x008\x03@\xd6\xfd\xdc\x01H\x04P\x00X\x00\x10\xed\xcf$\x12V\nP\n\x0b\x08\x96\xa1\xc8\x85\x05\x10\x00\x18\xc1\x04\x12\x0c\xe8\xbe\x89\xe5\xa4\x9c\xe9\x82\xa3\xe7\xbe\x8e\x18k \xe5\xad\xe2\x04(\xe5\xad\xe2\x042\x18\x08\x01\x10\x00\x18\x00 \x00(\x000\x008\x00@\x00H\x01P\x00X\x00`\x008\x02@\xf4\x9dTH\x02P\x0cX\xba\xb3\xbf\x0c\x10\xab\xd1$\x12V\nP\n\x0b\x08\xca\xa3\xfa\xe6\x04\x10\x00\x18\xb8\x04\x12\x0c\xe9\xbe\x99\xe5\xb4\x8e\xe9\x9b\xb7\xe5\xa4\xab\x18h \x91\xb0\xe2\x04(\x91\xb0\xe2\x042\x18\x08\x01\x10\x00\x18\x00 \x00(\x010\x008\x00@\x00H\x02P\x00X\x00`\x008\x00@\x84\x8eyH\x08P\x0cX\xc0\x9a\xbf\x0c\x10\x8b\xd0$\x12Z\nT\n\x0b\x08\x93\xc1\xdf\xfc\x05\x10\x00\x18\xba\x04\x12\x0f\xe9\x86\x89\xe2\x95\xad\xe3\x82\xa1\xe8\xa5\xbf\xe5\x87\xa8\x18p \xc9\xae\xe2\x04(\xc9\xae\xe2\x042\x18\x08\x00\x10\x00\x18\x00 \x00(\x000\x008\x00@\x00H\x01P\x00X\x00`\x008\x00@\xb8\x88\x94\x01H\x04P\x0cX\xac\xfb\xbf\x0c\x10\xed\xcf$\x12W\nQ\n\x0b\x08\xda\x98\xfd\x92\x01\x10\x00\x18\xa8\x04\x12\x0c\xe7\xbb\x88\xe3\x83\x9f\xe5\x85\xab\xe4\xba\x91\x18l \xc9\xae\xe2\x04(\xc9\xae\xe2\x042\x18\x08\x01\x10\x00\x18\x00 \x00(\t0\x008\x00@\x00H\x07P\x00X\x00`\x008\x00@\xae\xd1\xf3\x03H\x04P\x00X\x84\xe7\xbf\x0c\x10\xa1\xd1$\x1a\x08\x08\x03\x10\x02\x18\x00 \n'
    readable_result = protobuf_to_readable(test_data[36:])

    print(readable_result)