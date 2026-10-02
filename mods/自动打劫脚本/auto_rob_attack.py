MOD_INFO = {
    "id": "auto_rob_attack",
    "fit": "server->game:198935",
}

class AutoRobAttackMod:
    def __init__(self):
        pass

    def _load_config(self, path):
        pass

    # 组装请求列表命令
    def send_198935_action(self):
        client_198935_action = {
            "direction": "game->server",
            "content": "",
        }

    def enabled_init(self):
        return [self.send_198935_action()]