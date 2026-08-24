import os
import yaml

class Configs:
    def __init__(self):
        # resource_url
        self.resource_keywords = []
        # file_manager
        self.resource_save_path = ""
        # net_work
        self.net_max_connection = 50
        self.net_timeout = 60
        # system
        self.debug = False

    def initialization_configs(self, config_path="./config.yaml"):
        with open(config_path, "r") as file:
            config_dict = dict(yaml.safe_load(file))
            # resource_url
            resource_url_cfg = config_dict.get("resource_url", {})
            self.resource_keywords = list(resource_url_cfg.get("keywords", []))
            # file_manager
            file_manager_cfg = config_dict.get("file_manager", {})
            self.resource_save_path = str(file_manager_cfg.get("resource_save_path", "../essence_resource"))
            # net_work
            net_work_cfg = config_dict.get("net_work", {})
            self.net_max_connection = int(net_work_cfg.get("max_connection", 50))
            self.net_timeout = int(net_work_cfg.get("timeout", 60))
            # system
            system_cfg = config_dict.get("system", {})
            self.debug = bool(system_cfg.get("debug", False))


