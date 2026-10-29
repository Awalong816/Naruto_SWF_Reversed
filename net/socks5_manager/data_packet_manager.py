import logging
from typing import Any
from datetime import datetime
from dataclasses import dataclass, field

from utils import get_decrypt_manager

logging.basicConfig(level=logging.INFO)

@dataclass
class DataPack:
    direction: str
    direction_type: int
    command_id: int
    count: int
    value_data: bytes
    time_stamp: str | None = field(default=None)
    context: str | dict | None = field(default=None)
    uin: int | None = field(default=None) # 当前账号
    role_id: int | None = field(default=None) # 当前角色
    server_id: int | None = field(default=None) # 当前服务器
    is_decrypted: bool | None = field(default=None) # 是否已经TEA解密
    need_type_reverse: str | None = field(default=None) # 需要逆向二进制格式化的方式
    request_id: int | None = field(default=None)
    forward_response: bool = field(default=False) # 注入动作的回包是否透传给客户端（True 才会触发客户端 UI 效果）

    def update_data(self, data: bytes):
        self.value_data = data


class DataPacketManager:
    def __init__(self):
        self.header_size = 36
        self.magic = b'\x09\x01'
        self.cache = {
            "game->server": bytearray(),
            "server->game": bytearray(),
        }
        # 转发改写专用缓冲，与 parse_data 的分析缓冲互相独立，避免两边抢同一份流
        self.forward_cache = {
            "game->server": bytearray(),
            "server->game": bytearray(),
        }
        # 外部组件
        self.decrypt_manager = get_decrypt_manager()
        self.decrypt_need_command_id = [
            198935,
            198936,
        ]

    def build_action_bytes(self, action_pack: DataPack, request_id: int, role_id: int, server_id: int, uin: int) -> bytes:
        """
        mod产出的DataPack加密后，重新统计长度，组装request_id,加头，得到可发送的完整动作数据
        :param action_pack: mod产出的动作包，至少包含 direction、command_id 与 value_data
        :return: 36字节头 + TEA密文
        """
        spec = {
            "command_id": action_pack.command_id,
            "body": bytes(action_pack.value_data or b""),
            "request_id": request_id,
            "role_id": role_id,
            "server_id": server_id,
            "uin": uin,
        }
        result = self.decrypt_manager.encrypt_action_spec(spec)
        return result["data"]

    def rewrite_forward(self, session, direction: str, data: bytes) -> bytes:
        """
        转发前把整段数据切成完整包，改写包头里的请求 id 后再拼回去
        - game->server：客户端原始 id -> 会话代理 id，并登记还原映射
        - server->game：代理 id -> 客户端原始 id；属于注入动作的回包按 forward_response 决定透传还是吞掉
        没走完的半包留在缓冲里等下一段数据；非协议数据（如 <policy-file-request/>）原样放行
        :param session: 当前会话，持有发号器与两个映射表
        :param direction: 转发方向
        :param data: 本次从 socket 读到的原始分片
        :return: 改写后可转发给对端的字节流（可能比入参短，因为半包被压后）
        """
        buffer = self.forward_cache[direction]
        buffer.extend(data)
        out = bytearray()

        while len(buffer) >= 2:
            if buffer[:2] != self.magic:
                # 非本协议数据，原样放行，避免握手/短包被卡死在缓冲里
                out.extend(buffer)
                buffer.clear()
                break
            if len(buffer) < self.header_size:
                break
            count = int.from_bytes(buffer[2:4], "big")
            total = self.header_size + count
            if len(buffer) < total:
                break

            frame = bytearray(buffer[:total])
            del buffer[:total]
            command_id = int.from_bytes(frame[4:8], "big")
            request_id = int.from_bytes(frame[8:12], "big")

            if direction == "game->server":
                proxy_id = session.new_proxy_id()
                session.out_index_map[(command_id, proxy_id)] = request_id
                frame[8:12] = proxy_id.to_bytes(4, "big")
            else:
                if (command_id, request_id) in session.out_index_map:
                    # 客户端自己请求的回包，还原成客户端原本的号
                    frame[8:12] = session.out_index_map.pop((command_id, request_id)).to_bytes(4, "big")
                elif request_id in session.injected:
                    action_pack = session.injected.pop(request_id)
                    if not action_pack.forward_response:
                        continue # 吞掉，客户端不会看到这条回包

            out.extend(frame)

        return bytes(out)

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
                count = int.from_bytes(completed_data[2:4],"big")
                command_id = int.from_bytes(completed_data[4:8],"big")
                request_id = int.from_bytes(completed_data[8:12],"big")
                direction_type = int.from_bytes(completed_data[12:16],"big")
                uin = int.from_bytes(completed_data[24:28],"big")
                role_id = int.from_bytes(completed_data[28:30],"big")
                server_id = int.from_bytes(completed_data[30:32],"big")
                if command_id in self.decrypt_need_command_id:
                    value_data = self.decrypt_manager.decrypt_data(completed_data)
                    is_decrypted = True
                else:
                    value_data = completed_data
                    is_decrypted = False

                data_packet = DataPack(
                    direction=direction,
                    direction_type=direction_type,
                    context=context,
                    uin=uin,
                    role_id=role_id,
                    server_id=server_id,
                    request_id=request_id,
                    time_stamp=time_stamp,
                    command_id=command_id,
                    count=count,
                    value_data=value_data,
                    is_decrypted=is_decrypted,
                )
                if debug:
                    self._log_report(data_packet,
                                     aim_id=[198935,198936],
                                     dismiss_id=[250882],
                                     )
                data_packets.append(data_packet)
            return data_packets
        except Exception as err:
            logging.warning(f"{err}")
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
        print(f"请求 ID: {data_pack.request_id}")
        print(f"有效长度: {data_pack.count}")
        if data_pack.is_decrypted:
            print(f"已经过 TEA 解密")
        print(f"原始字节流: {data_pack.value_data}")
        print(f"原始字节HEX: {data_pack.value_data[:min(len(data_pack.value_data),256)].hex(' ')}")
        print("*"*100)
        print("\n")


def get_data_packet_manager():
    return DataPacketManager()


if __name__ == "__main__":
    pass