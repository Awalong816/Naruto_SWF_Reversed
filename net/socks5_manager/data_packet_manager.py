from datetime import datetime


class DataPacketManager:
    def __init__(self):
        self.version = "26.9.28"

    @staticmethod
    def parse_data_packet(data: bytes, debug=False, **kwargs):
        context = kwargs.get("context")
        direction = kwargs.get("direction")

        length = len(data)
        if length < 36:
            raise ValueError("数据长度不符合要求")

        _magic = data[:2]
        _count = data[2:4]
        _command_id = data[4:8]
        _request_id = data[8:12]
        _direction_type = data[12:16]
        # _role_id = data[28:30]
        # _server_id = data[30:32]
        # _client_ip = data[32:36]

        if _magic != b'\x00\x01':
            raise ValueError(f"协议头magic不符合要求: {_magic}")

        command_id = int.from_bytes(_command_id, "big")
        direction_type = _direction_type[-1]

        if _count[0] == 1:
            count = int.from_bytes(_count, "little")
        else:
            count = int.from_bytes(_count, "big")
        body_start = 36
        body_end = body_start + count

        body = data[body_start:body_end]

        if debug:
            print("*" * 100)
            print(f"[EVENT] {direction}")
            print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"上下文: {context}")
            print(f"长度: {length}")
            print(f"原始内容: {data}")
            print(f"原始HEX: {data[:min(len(data), 256)].hex(' ')}\n")

            print(f"有效数据体长度: {count}")
            print(f"动作/指令 ID: {command_id}")

            direction_description = ""
            if direction_type == 0x01:
                direction_description = "1-客户端请求"
            elif direction_type == 0x02:
                direction_description = "2-服务器响应"
            elif direction_type == 0x03:
                direction_description = "3-服务器主动推送"
            print(f"数据方向类型: {direction_description}")
            print("*" * 100)
            print("\n")

def get_data_packet_manager():
    return DataPacketManager()


if __name__ == "__main__":
    pass