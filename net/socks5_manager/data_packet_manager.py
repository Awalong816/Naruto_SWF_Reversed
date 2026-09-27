import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

class DataPack:
    def __init__(self, **kwargs):
        self.direction = kwargs.get("direction")
        self.direction_type = kwargs.get("direction_type")
        self.context = kwargs.get("context")
        self.time_stamp = kwargs.get("time_stamp")
        self.command_id = kwargs.get("command_id")
        self.count = kwargs.get("count")
        self.data = kwargs.get("data")

    def update_data(self, data: bytes):
        self.data = data


class DataPacketManager:
    def __init__(self):
        self.header_size = 36
        self.magic = b'\x09\x01'
        self.cache = {
            "game->server": bytearray(),
            "server->game": bytearray(),
        }

    def completed_data_stream(self, direction: str, data: bytes):
        """
        **一对n核心**
        一段数据输出0~n个完整包，不负责分析，只负责切分
        :param direction:
        :param data:
        :return:
        """
        buffer = self.cache.get(direction)
        buffer.extend(data)
        completed_datas = []

        while len(buffer) >= self.header_size: # 协议本身允许出现body长度为0的整包
            if buffer[:2] != self.magic:
                raise Exception("失去同步")
            count = int.from_bytes(
                buffer[2:4],
                "big",
            )
            if len(buffer) >= self.header_size + count:
                completed_datas.append(bytes(buffer[:self.header_size + count]))
                del buffer[:self.header_size + count]
            else:
                break

        return completed_datas


def get_data_packet_manager():
    return DataPacketManager()


if __name__ == "__main__":
    pass