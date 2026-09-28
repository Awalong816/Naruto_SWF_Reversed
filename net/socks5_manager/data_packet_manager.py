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
        self.command_info = kwargs.get("command_info")
        self.count = kwargs.get("count")
        self.data = kwargs.get("data")

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


    def parse_data(self, context, direction: str, data: bytes, debug=False):
        time_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            completed_datas = self.completed_data_stream(direction, data) # 粘包不改变方向
            if not completed_datas:
                return
            data_packets = []
            for completed_data in completed_datas:
                data_packet = DataPack(
                    direction=direction,
                    direction_type=completed_data[15],
                    context=context,
                    time_stamp=time_stamp,
                    command_id=int.from_bytes(completed_data[4:8],"big"),
                    count=int.from_bytes(completed_data[2:4],"big"),
                    data=completed_data,
                )
                if debug:
                    self._report(data_packet)
                data_packets.append(data_packet)

        except Exception as err:
            logging.warning(f"[WARN] {err}")

    @staticmethod
    def _report(data_pack: DataPack):
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