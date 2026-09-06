import ctypes
import socket
import ipaddress
import logging
from pathlib import Path

from config import Configs

logging.basicConfig(level=logging.INFO) # 最低播报等级

class DNSManager:
    def __init__(self):
        pass

    def domain2ip(self, domain:str):
        """
        通用方法: 域名转ip地址
        使用dns先获得 zone.huoying.qq.com 的真实ipv4地址
        :param domain: 目标域名字符串
        :return: ipv4字符串列表
        """
        try:
            address_info = socket.getaddrinfo(
                host=domain,
                port=None,
                family=socket.AF_INET  # 地址族 AF_INET=只返回ipv4;AF_INET=只返回ipv6;AF_UNSPEC=返回4和6
            )
            # 输出类似:
            # [(<AddressFamily.AF_INET: 2>, <SocketKind.SOCK_STREAM: 1>, 6, '', ('110.242.68.66', 0)),
            #  (<AddressFamily.AF_INET: 2>, <SocketKind.SOCK_DGRAM: 2>, 17, '', ('110.242.68.66', 0)),
            #  (<AddressFamily.AF_INET: 2>, <SocketKind.SOCK_RAW: 3>, 0, '', ('110.242.68.66', 0))]
            ips = []

            if address_info:
                for info in address_info:
                    ips.append(info[4][0])
                return ips
            else:
                return None

        except socket.gaierror:
            return None


def get_dns_manager():
    return DNSManager()


if __name__ == "__main__":
    pass
    # ** v9.7失败,在entry之前就已经是具体ip，所以修改翻译规则无效，因为进程有自己的翻译规则/映射 **
    # manager = get_dns_manager()
    # domain = "zone.huoying.qq.com"
    # port = 10494
    # cfg = Configs()
    # cfg.initialization_configs(config_path=r"E:\pythonProject\启动器\config.yaml")
    # cfg.send_server_domain = domain
    # cfg.send_server_prot = port
    # original_ips = manager.domain2ip(domain)
    # cfg.send_server_ips = original_ips
    # manager.host_rule_replace(cfg=cfg)
    # input(f"输入任意+回车结束:") # 阻塞测试
    # manager.reset_rule_replace(cfg=cfg)

