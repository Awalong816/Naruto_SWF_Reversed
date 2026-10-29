import logging
import os
import json
from datetime import datetime
from pathlib import Path

from net.socks5_manager.data_packet_manager import DataPack
from net.socks5_manager.mod_manager import BaseMod

# 模组信息提到类顶方便提取
MOD_INFO = {
    "id": "auto_rob_attack", # mod标识
    "name": "自动打劫脚本", # 前端展示名称
    "fit": [
        {
            "direction": "server->game",
            "command_id": 198935,
            "time_slot": [("11:00", "14:30"),("18:00", "21:30")],
            "data_type": "protobuf",
        },
    ]
}

# =============================================================================

RET_INFO_SCHEMA = {
    1: {
        "name": "code",
        "type": "int32",
    },
    2: {
        "name": "message",
        "type": "string",
    },
}


PLAYER_KEY_SCHEMA = {
    1: {
        "name": "uin",
        "type": "uint32",
    },
    2: {
        "name": "role_id",
        "type": "uint32",
    },
    3: {
        "name": "server_id",
        "type": "uint32",
    },
}


DIAMOND_INFO_SCHEMA = {
    1:  {"name": "blue_level", "type": "int32"},
    2:  {"name": "blue_common", "type": "bool"},
    3:  {"name": "blue_year", "type": "bool"},
    4:  {"name": "blue_super", "type": "bool"},

    5:  {"name": "yellow_level", "type": "int32"},
    6:  {"name": "yellow_common", "type": "bool"},
    7:  {"name": "yellow_year", "type": "bool"},
    8:  {"name": "yellow_super", "type": "bool"},

    9:  {"name": "qq_level", "type": "int32"},
    10: {"name": "qq_common", "type": "bool"},
    11: {"name": "qq_year", "type": "bool"},
    12: {"name": "qq_super", "type": "bool"},
}


PLAYER_BASE_INFO_SCHEMA = {
    1: {
        "name": "player_key",
        "type": "message",
        "schema": PLAYER_KEY_SCHEMA,
    },
    2: {
        "name": "name",
        "type": "string",
    },
    3: {
        "name": "level",
        "type": "uint32",
    },
    4: {
        "name": "show_ninja",
        "type": "uint32",
    },
    5: {
        "name": "tabard_ninja",
        "type": "uint32",
    },
    6: {
        "name": "diamond_info",
        "type": "message",
        "schema": DIAMOND_INFO_SCHEMA,
    },
    7: {
        "name": "vip_level",
        "type": "enum",
    },
    8: {
        "name": "history_max_combat_power",
        "type": "sint32",
    },
    9: {
        "name": "role_category",
        "type": "sint32",
    },
    10: {
        "name": "battle_royale_craft_limit",
        "type": "sint32",
    },
    11: {
        "name": "fashion_id",
        "type": "sint32",
    },
}


ROB_INFO_SCHEMA = {
    1: {
        "name": "base_info",
        "type": "message",
        "schema": PLAYER_BASE_INFO_SCHEMA,
    },
    2: {
        "name": "task_id",
        "type": "int32",
    },
}


ROB_TIMES_INFO_SCHEMA = {
    1: {
        "name": "can_rob_times",
        "type": "int32",
    },
    2: {
        "name": "remaining_rob_times",
        "type": "int32",
    },
    3: {
        "name": "free_times",
        "type": "int32",
    },
    4: {
        "name": "need_gold_ingot_num",
        "type": "int32",
    },
    5: {
        "name": "rob_item_num",
        "type": "int32",
    },
}


ROB_LIST_RESPONSE_SCHEMA = {
    1: {
        "name": "ret_info",
        "type": "message",
        "schema": RET_INFO_SCHEMA,
    },
    2: {
        "name": "rob_list",
        "type": "message",
        "schema": ROB_INFO_SCHEMA,
        "repeated": True,
    },
    3: {
        "name": "times_info",
        "type": "message",
        "schema": ROB_TIMES_INFO_SCHEMA,
    },
}
# task_id = area + hard(镖型*SS=5)映射方式 *每个hard等级对应7条,主要是设计对铜币镖奖励的区别,点卷镖内容没有实际区别*
SS_TASK_IDS = {
    *range(600011, 600018), # 波之国
    *range(600041, 600048), # 短册街
    *range(600071, 600078), # 雨忍村内
    *range(600101, 600108), # 五封结界
    *range(600131, 600138), # 风之国沙漠
    *range(600161, 600168), # 火之寺
    *range(600191, 600198), # 沙忍村北
    *range(600221, 600228), # 雨忍村北
}

# =============================================================================


class AutoRobAttackMod(BaseMod):
    MOD_INFO = MOD_INFO

    def __init__(self):
        # 继承成员
        # 自带:
        # enabled = false
        super().__init__()
        # 自带成员
        self.config_path: Path | None
        self.attack_list = []

    # ============= 自我方法 =============
    @staticmethod
    def _zigzag_decode(value: int) -> int:
        """Protobuf sint32/sint64 转有符号整数"""
        return (value >> 1) ^ -(value & 1)

    @staticmethod
    def _get_time_slots():
        fits = MOD_INFO.get("fit", [])
        if not fits:
            return None
        time_slots = fits[0].get("time_slot")
        return time_slots

    @staticmethod
    def _time_pass(time_slots, now=None):
        now = now or datetime.now()
        now_time = now.time()

        for slot_start, slot_end in time_slots:
            start = datetime.strptime(slot_start, "%H:%M").time()
            end = datetime.strptime(slot_end, "%H:%M").time()

            if start <= end and start <= now_time <= end:
                return True
        return False

    # 组装请求列表命令
    @staticmethod
    def send_198935_action() -> DataPack:
        # TODO: 做成DataPack交给data_packet_manager转回bytes
        action_spec = DataPack(
            # mod侧负责
            direction="game->server",
            direction_type=1,
            command_id=198935,
            count=0,
            value_data=b'',
            need_type_reverse=None,
        )
        return action_spec

    def _apply_schema(self, fields: list | dict, schema: dict = ROB_LIST_RESPONSE_SCHEMA):
        """
        把 _read_protobuf() 得到的数字字段列表，
        根据 schema 转成带业务字段名的字典。
        """
        result = {}

        for item in fields:
            field_number = item["field"]
            value = item.get("value")

            definition = schema.get(field_number)

            # AS协议中还没登记的字段
            if definition is None:
                name = f"unknown_{field_number}"

                if name in result:
                    if not isinstance(result[name], list):
                        result[name] = [result[name]]
                    result[name].append(value)
                else:
                    result[name] = value

                continue

            name = definition["name"]
            field_type = definition["type"]
            repeated = definition.get("repeated", False)

            if field_type == "message":
                child_schema = definition["schema"]

                if not isinstance(value, list):
                    parsed_value = value
                else:
                    parsed_value = self._apply_schema(value, child_schema)

            elif field_type == "sint32":
                parsed_value = self._zigzag_decode(value)

            elif field_type == "bool":
                parsed_value = bool(value)

            else:
                # int32、uint32、enum、string等，
                # 当前_read_protobuf已经得到对应Python值
                parsed_value = value

            if repeated:
                result.setdefault(name, []).append(
                    parsed_value
                )
            else:
                result[name] = parsed_value

        return result

    def _protobuf2readable(self, data: list | dict):
        schema_data = self._apply_schema(data)
        rob_list = schema_data.get("rob_list", [])
        format_rob_list = []
        for item in rob_list:
            base_info = item.get("base_info", {})
            if not base_info:
                continue
            try:
                format_rob_list.append(
                    {
                        "name": base_info["name"],
                        "server_id": base_info["player_key"]["server_id"],
                        "uin": base_info["player_key"]["uin"],
                        "task_id": item["task_id"],
                    }
                )
            except Exception:
                continue
        return format_rob_list

    def _save_attack_list_config(self):
        with open(self.config_path, "r", encoding="utf-8") as file:
            cfg_data = json.load(file)
            if self.attack_list and cfg_data and cfg_data.get("attack_list", []):
                cfg_data["attack_list"] = self.attack_list
                self.config_path.write_text(json.dumps(
                        cfg_data,
                        ensure_ascii=False,
                        indent=4,
                    ),
                    encoding="utf-8"
                )

    def load_config(self, path=None):
        if not path:
            dir_path = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(dir_path, r"脚本配置.json")

        cfg_path = Path(path)
        self.config_path = cfg_path
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                cfg_data = json.load(file)
        except Exception as err:
            raise err

        attack_list = cfg_data.get("attack_list",[])
        if len(attack_list) == 0:
            raise ValueError("配置文件不完整或列表为空")

        sorted_attack_list = sorted(attack_list, key=lambda item: item["priority"])
        self.attack_list = sorted_attack_list

    def recv_198935_action(self):
        # 198935 使用protobuf二进制数据格式
        pass

    # ============= 继承方法 =============
    def _enabled_init(self, now=None, **kwargs) -> list[DataPack]:
        """启用时的初始化：now 由管理器统一传入（datetime），缺省才回落本机时间"""
        # 时间限制
        # time_slots = self._get_time_slots()
        # if not time_slots:
        #     raise ValueError("fit 缺失字段 'time_slots'")
        #
        # if time_slots and (not self._time_pass(time_slots, now=now)):
        #     raise ValueError("不在可运行的时间段内")
        # 启动动作
        action_specs = [
            self.send_198935_action(),
        ]
        return action_specs

    def start(self, now=None, **kwargs) -> list[DataPack]:
        try:
            self.enabled = True
            action_specs = self._enabled_init(now=now)
            return action_specs
        except Exception as err:
            self.enabled = False
            raise err

    def stop(self, now=None, **kwargs):
        self.enabled = False

    def event_trigger(self, data, now=None, **kwargs):
        # 时间限制
        time_slots = self._get_time_slots()
        if not time_slots:
            self.enabled = False
            raise ValueError("fit 缺失字段 'time_slots'")

        if time_slots and (not self._time_pass(time_slots, now=now)):
            self.enabled = False
            raise ValueError("不在可运行的时间段内")

        # 业务内容
        if not isinstance(data, list):
            raise TypeError(f"<auto_rob_attack event_trigger> only support list input")
        format_data = self._protobuf2readable(data)
        print(format_data)
        for index, aim in enumerate(self.attack_list):
            # 每个session一个实例，不需要上锁
            aim_name = aim["name"]
            aim_uin = aim["uin"]
            aim_zone_id = aim["zone_id"]

            for item in format_data:
                print(f"aim:{aim_name}: {aim_zone_id} -- item:{item.get('name')}:{item.get('server_id')}")
                if (item.get("name") == aim_name or item.get("uin") == aim_uin) and (
                        item.get("server_id") == aim_zone_id):
                    if not aim_uin and item.get("uin"):
                        self.attack_list[index]["uin"] = item.get("uin")
                        try:
                            self._save_attack_list_config()
                            logging.info(f"更新 mod <auto_rob_attack> 配置文件成功")
                        except Exception as err:
                            logging.warning(f"更新 mod <auto_rob_attack> 配置文件失败: {err}")
                    if item.get("task_id") in SS_TASK_IDS:
                        self.enabled = False # 成功进入战斗后退出脚本
                        print("找到")
                        # TODO: find aim 发送198936
                        return

        print("没有找到")
        # TODO: 没有找到，继续循环出发198935
        action_specs = [
            self.send_198935_action()
        ]
        return action_specs


SERVER_MOD_CLASS = AutoRobAttackMod


def test(data: list | dict):
    mod = AutoRobAttackMod()
    mod.load_config()
    result = mod.event_trigger(data)
    # mod._enabled_init()
    return result


if __name__ == "__main__":
    test_data = [{'field': 1, 'wire_type': 2, 'length': 11, 'value': [{'field': 1, 'wire_type': 0, 'value': 0}, {'field': 2, 'wire_type': 2, 'length': 7, 'value': 'success'}]}, {'field': 2, 'wire_type': 2, 'length': 83, 'value': [{'field': 1, 'wire_type': 2, 'length': 77, 'value': [{'field': 1, 'wire_type': 2, 'length': 10, 'value': [{'field': 1, 'wire_type': 0, 'value': 120234598}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 507}]}, {'field': 2, 'wire_type': 2, 'length': 12, 'value': '忘川河神'}, {'field': 3, 'wire_type': 0, 'value': 111}, {'field': 4, 'wire_type': 0, 'value': 10000201}, {'field': 5, 'wire_type': 0, 'value': 10000201}, {'field': 6, 'wire_type': 2, 'length': 24, 'value': [{'field': 1, 'wire_type': 0, 'value': 1}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 0}, {'field': 4, 'wire_type': 0, 'value': 0}, {'field': 5, 'wire_type': 0, 'value': 1}, {'field': 6, 'wire_type': 0, 'value': 0}, {'field': 7, 'wire_type': 0, 'value': 0}, {'field': 8, 'wire_type': 0, 'value': 0}, {'field': 9, 'wire_type': 0, 'value': 7}, {'field': 10, 'wire_type': 0, 'value': 0}, {'field': 11, 'wire_type': 0, 'value': 0}, {'field': 12, 'wire_type': 0, 'value': 0}]}, {'field': 7, 'wire_type': 0, 'value': 3}, {'field': 8, 'wire_type': 0, 'value': 3620566}, {'field': 9, 'wire_type': 0, 'value': 4}, {'field': 10, 'wire_type': 0, 'value': 0}, {'field': 11, 'wire_type': 0, 'value': 0}]}, {'field': 2, 'wire_type': 0, 'value': 600045}]}, {'field': 2, 'wire_type': 2, 'length': 86, 'value': [{'field': 1, 'wire_type': 2, 'length': 80, 'value': [{'field': 1, 'wire_type': 2, 'length': 11, 'value': [{'field': 1, 'wire_type': 0, 'value': 1353846934}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 577}]}, {'field': 2, 'wire_type': 2, 'length': 12, 'value': '辉夜那美'}, {'field': 3, 'wire_type': 0, 'value': 107}, {'field': 4, 'wire_type': 0, 'value': 10000101}, {'field': 5, 'wire_type': 0, 'value': 10000101}, {'field': 6, 'wire_type': 2, 'length': 24, 'value': [{'field': 1, 'wire_type': 0, 'value': 1}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 0}, {'field': 4, 'wire_type': 0, 'value': 0}, {'field': 5, 'wire_type': 0, 'value': 0}, {'field': 6, 'wire_type': 0, 'value': 0}, {'field': 7, 'wire_type': 0, 'value': 0}, {'field': 8, 'wire_type': 0, 'value': 0}, {'field': 9, 'wire_type': 0, 'value': 1}, {'field': 10, 'wire_type': 0, 'value': 0}, {'field': 11, 'wire_type': 0, 'value': 0}, {'field': 12, 'wire_type': 0, 'value': 0}]}, {'field': 7, 'wire_type': 0, 'value': 2}, {'field': 8, 'wire_type': 0, 'value': 1380084}, {'field': 9, 'wire_type': 0, 'value': 2}, {'field': 10, 'wire_type': 0, 'value': 12}, {'field': 11, 'wire_type': 0, 'value': 26204602}]}, {'field': 2, 'wire_type': 0, 'value': 600235}]}, {'field': 2, 'wire_type': 2, 'length': 86, 'value': [{'field': 1, 'wire_type': 2, 'length': 80, 'value': [{'field': 1, 'wire_type': 2, 'length': 11, 'value': [{'field': 1, 'wire_type': 0, 'value': 1289654730}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 568}]}, {'field': 2, 'wire_type': 2, 'length': 12, 'value': '龙崎雷夫'}, {'field': 3, 'wire_type': 0, 'value': 104}, {'field': 4, 'wire_type': 0, 'value': 10000401}, {'field': 5, 'wire_type': 0, 'value': 10000401}, {'field': 6, 'wire_type': 2, 'length': 24, 'value': [{'field': 1, 'wire_type': 0, 'value': 1}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 0}, {'field': 4, 'wire_type': 0, 'value': 0}, {'field': 5, 'wire_type': 0, 'value': 1}, {'field': 6, 'wire_type': 0, 'value': 0}, {'field': 7, 'wire_type': 0, 'value': 0}, {'field': 8, 'wire_type': 0, 'value': 0}, {'field': 9, 'wire_type': 0, 'value': 2}, {'field': 10, 'wire_type': 0, 'value': 0}, {'field': 11, 'wire_type': 0, 'value': 0}, {'field': 12, 'wire_type': 0, 'value': 0}]}, {'field': 7, 'wire_type': 0, 'value': 0}, {'field': 8, 'wire_type': 0, 'value': 1984260}, {'field': 9, 'wire_type': 0, 'value': 8}, {'field': 10, 'wire_type': 0, 'value': 12}, {'field': 11, 'wire_type': 0, 'value': 26201408}]}, {'field': 2, 'wire_type': 0, 'value': 600075}]}, {'field': 2, 'wire_type': 2, 'length': 90, 'value': [{'field': 1, 'wire_type': 2, 'length': 84, 'value': [{'field': 1, 'wire_type': 2, 'length': 11, 'value': [{'field': 1, 'wire_type': 0, 'value': 1603788947}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 570}]}, {'field': 2, 'wire_type': 2, 'length': 15, 'value': '醉╭ァ西凨'}, {'field': 3, 'wire_type': 0, 'value': 112}, {'field': 4, 'wire_type': 0, 'value': 10000201}, {'field': 5, 'wire_type': 0, 'value': 10000201}, {'field': 6, 'wire_type': 2, 'length': 24, 'value': [{'field': 1, 'wire_type': 0, 'value': 0}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 0}, {'field': 4, 'wire_type': 0, 'value': 0}, {'field': 5, 'wire_type': 0, 'value': 0}, {'field': 6, 'wire_type': 0, 'value': 0}, {'field': 7, 'wire_type': 0, 'value': 0}, {'field': 8, 'wire_type': 0, 'value': 0}, {'field': 9, 'wire_type': 0, 'value': 1}, {'field': 10, 'wire_type': 0, 'value': 0}, {'field': 11, 'wire_type': 0, 'value': 0}, {'field': 12, 'wire_type': 0, 'value': 0}]}, {'field': 7, 'wire_type': 0, 'value': 0}, {'field': 8, 'wire_type': 0, 'value': 2425912}, {'field': 9, 'wire_type': 0, 'value': 4}, {'field': 10, 'wire_type': 0, 'value': 12}, {'field': 11, 'wire_type': 0, 'value': 26213804}]}, {'field': 2, 'wire_type': 0, 'value': 600045}]}, {'field': 2, 'wire_type': 2, 'length': 87, 'value': [{'field': 1, 'wire_type': 2, 'length': 81, 'value': [{'field': 1, 'wire_type': 2, 'length': 11, 'value': [{'field': 1, 'wire_type': 0, 'value': 308235354}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 552}]}, {'field': 2, 'wire_type': 2, 'length': 12, 'value': '终ミ八云'}, {'field': 3, 'wire_type': 0, 'value': 108}, {'field': 4, 'wire_type': 0, 'value': 10000201}, {'field': 5, 'wire_type': 0, 'value': 10000201}, {'field': 6, 'wire_type': 2, 'length': 24, 'value': [{'field': 1, 'wire_type': 0, 'value': 1}, {'field': 2, 'wire_type': 0, 'value': 0}, {'field': 3, 'wire_type': 0, 'value': 0}, {'field': 4, 'wire_type': 0, 'value': 0}, {'field': 5, 'wire_type': 0, 'value': 9}, {'field': 6, 'wire_type': 0, 'value': 0}, {'field': 7, 'wire_type': 0, 'value': 0}, {'field': 8, 'wire_type': 0, 'value': 0}, {'field': 9, 'wire_type': 0, 'value': 7}, {'field': 10, 'wire_type': 0, 'value': 0}, {'field': 11, 'wire_type': 0, 'value': 0}, {'field': 12, 'wire_type': 0, 'value': 0}]}, {'field': 7, 'wire_type': 0, 'value': 0}, {'field': 8, 'wire_type': 0, 'value': 8186030}, {'field': 9, 'wire_type': 0, 'value': 4}, {'field': 10, 'wire_type': 0, 'value': 0}, {'field': 11, 'wire_type': 0, 'value': 26211204}]}, {'field': 2, 'wire_type': 0, 'value': 600225}]}, {'field': 3, 'wire_type': 2, 'length': 8, 'value': [{'field': 1, 'wire_type': 0, 'value': 3}, {'field': 2, 'wire_type': 0, 'value': 2}, {'field': 3, 'wire_type': 0, 'value': 0}, {'field': 4, 'wire_type': 0, 'value': 10}]}]
    test_result = test(test_data)
    print(test_result)