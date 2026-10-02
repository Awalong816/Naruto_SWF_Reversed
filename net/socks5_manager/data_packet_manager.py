import logging
from datetime import datetime
from typing import Any
from dataclasses import dataclass

from utils import get_decrypt_manger

logging.basicConfig(level=logging.INFO)

@dataclass
class DataPack:
    direction: str
    direction_type: int
    context: str | dict
    time_stamp: str
    command_id: int
    count: int
    data: bytes
    command_info: Any = None

    def update_data(self, data: bytes):
        self.data = data

    def parse_command_info(self):
        pass


class DataPacketManager:
    def __init__(self):
        self.header_size = 36
        self.magic = b'\x09\x01'
        self.cache = {
            "game->server": bytearray(),
            "server->game": bytearray(),
        }

        self.decrypt_manager = get_decrypt_manger()
        self.decrypt_need_command_id = [
            198935,
            198936,
        ]

    def build_action_packet(self, action_spec: dict):
        pass

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
                raise Exception(f"失去同步"
                                f"direction={direction}, "
                                f"head={bytes(buffer[:32])!r}, "
                                f"hex={bytes(buffer[:32]).hex(' ')}"
                                )
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


    def parse_data(self, context, direction: str, data: bytes, debug=False):
        time_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            completed_datas = self.completed_data_stream(direction, data) # 粘包不改变方向
            if not completed_datas:
                return
            data_packets = []
            for completed_data in completed_datas:
                direction_type = completed_data[15]
                command_id = int.from_bytes(completed_data[2:4],"big")
                count = int.from_bytes(completed_data[2:4],"big")
                if command_id in self.decrypt_need_command_id:
                    value_data = self.decrypt_manager.decrypt_data(completed_data)
                else:
                    value_data = completed_data
                data_packet = DataPack(
                    direction=direction,
                    direction_type=direction_type,
                    context=context,
                    time_stamp=time_stamp,
                    command_id=command_id,
                    count=count,
                    data=value_data,
                )
                if debug:
                    self._log_report(data_packet,)
                data_packets.append(data_packet)
            return data_packets
        except Exception as err:
            logging.warning(f"[WARN] {err}")
            return

    @staticmethod
    def _log_report(data_pack: DataPack, aim_id=None, dismiss_id=None):
        # 筛选
        if aim_id:
            if data_pack.command_id not in aim_id:
                return
        if dismiss_id:
            if data_pack.command_id in dismiss_id:
                return
        # 日志展示
        print("*"*100)
        print(f"[EVENT] {data_pack.direction}")
        print(f"时间: {data_pack.time_stamp}")
        print(f"上下文: {data_pack.context}")
        print(f"类型: ",end="")
        if data_pack.direction_type == 1:
            print("客户端请求")
        elif data_pack.direction_type == 2:
            print("服务器响应")
        elif data_pack.direction_type == 3:
            print("服务器推送")
        else:
            print("未知")
        print(f"指令/动作 ID: {data_pack.command_id}")
        print(f"有效长度: {data_pack.count}")
        print(f"原始字节流: {data_pack.data}")
        print(f"原始字节HEX: {data_pack.data[:min(len(data_pack.data),256)].hex(' ')}")
        print("*"*100)
        print("\n")


def get_data_packet_manager():
    return DataPacketManager()


if __name__ == "__main__":
    pass