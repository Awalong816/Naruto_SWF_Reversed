from dataclasses import dataclass


MOD_INFO = {
    "id": "auto_rob_attack",
    "fit": "server->game:198935",
}


@dataclass
class AttackPlayerInfo:
    Name: str
    Zone_id: int
    Uin: int


class AutoRobAttackMod:
    def __init__(self):
        pass

    def _load_config(self, path):
        pass

    def recv_198935_action(self):
        # 198935 使用protobuf二进制数据格式
        pass

    # 组装请求列表命令
    def send_198935_action(self):
        client_198935_action = {
            "direction": "game->server",
            "content": "",
        }

    def enabled_init(self):
        return [self.send_198935_action()]