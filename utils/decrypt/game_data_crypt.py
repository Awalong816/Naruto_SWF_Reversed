import secrets
import struct


class GameDataCryptManager:
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
            "data": data,
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
            "direction": "game->server",
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
    return GameDataCryptManager()


if __name__ == "__main__":
    server = GameDataCryptManager()
    test_data = b'\t\x01\x01\xe8\x00\x03\t\x17\x00\x00\x01i\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00G_I\x8a\x00\x00\x01\xfa\x00\x00\x00\x00iu\x87ym\xfc\x88\xa7I\x8d\x8a#`\xcd}H\x9bT@b3\x1d\xf6\x06\x1b\xcf\x16\xa8x=\xc8v\x1ct\xb4\xa7&\xefUbH\x00z\xc4\x8a\xd5\xa0W6\xa0Q\x0e\xa1\xadd\xb4mIH\x1d\xd2=\xcb\x7f\xc6\x94\xac\xfb\x9cM\x87\x04\x18bz\xd3/\xb5\x7f\x06r\xeb\xa9CM\xde\x8c\xd8k\xd7d\x7ff9\xd4\xce\xbd\xa3\xe4\x11#\x97C\xfb\xe5\x8d1.\xc6\x01\x85\xc9q\xd9\xb6\x0b\xebB~\xaf$j\x87\x13\xd15\xae{rcK\xectX\xbe\x17I\xf2!\xc0\x16\xb9\x9bc\xe2Op]L\xcf4\x91\xc9\x02\x00\x0f\x11\xe7\xf5\x86\x04;\xae%"\x9d\xdb\xf6\xe5\xbf1\xa2W\x9f\x83\xa2\x86\xa6\xbbB\xb7\x12\xaf\x11\xb8\xce#\xb0Z\xf6\x83\xe0,\xd0\xb7Le\xe3\xcb\xb5\x16c\n\xa5\xd5\x9d\x84\n\xee\x98\x8a\x05\xdb\xe3\xca0\xd8\n\xc6+\xb7\x86j\x8b\xd0\xd2\x9b\x8c,\xb5\xbc\xd4\x95\xa2\x06\xfc\xd3N\xe4\xf8\xdb\xee\x90f\xe1\xe6\xa8\xd5\xe3{#=\xce\xf3p\to|\xc7\xc53\x8a\xd6\x17\x7fqf\x97k[\xea]E\xf1o\x1fOo\xf5\xdd\xf2\xc9\x03\x89\x8as\xce0U\x81\x07\xd7=\x85\x97?\xc1\xaf\xa0\xf5\xcf\xe6\x9a\xccf\xc5\xd6\x95\x96\xc5.\xd9\xa3.\xb6J\xe8\x11\x07\xe2\x8ev\xdb\xf9\xc9\x80\x9f-H\xe4\x03\x1f\x9c\xeb\xe2]\x01\xeb\x062sy\x8e\x07=\xc8HY\xdb\xf4\x86\xe1E<\xb1J\x84`\xed\x13\xa18tg\xcd\x13\xb1\xa4iju\xfe\xf0\x9c\xdf\x1fg\xc9$\xa1\xf9\xa9yjJ\xca\x8d\x08\x93?QI\x17U\x9e\n\xd9\x8e>\xb7\x0e\x07d2\x1aD\x8b\xc0\xf8\x87&t2=`~>`\xdf\x90\x99`\x8bE<\xe2\xe7\x05\xc6\x17\x13\xc1\x19\xf6\xf4\xf9`\x00k\x00$\x1c\xb5Gqa\x8f\xa8D\xdd\x8d\x0f\x9a\x92\xd2\x99M\xf5\x9c\xe3\x06@W\x964\xf9\xc4j\xa8\xb4<\xf1\xd5\xa9\xdb5)\xbd\xe5#\xa6_8\xab\n\xa9\xfd\x1e'
    result = server.decrypt(test_data)
    print(result)

    print("command_id:", result["command_id"])
    print("request_id:", result["request_id"])
    print("message_type:", result["message_type"])

    print("密文长度:", len(result["encrypted_body"]))
    print("明文长度:", len(result["body"]))

    print("protobuf HEX:")
    print(result["body"].hex(" "))