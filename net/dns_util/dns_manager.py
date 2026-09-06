import ctypes
import socket
import ipaddress

from config import Configs

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

    def host_rule_replace(self, cfg: Configs):
        host_mark_start = "# NARUTO PY PROXY BEGIN"
        host_mark_end = "# NARUTO PY PROXY END"

        # 开始替换
        domain = cfg.send_server_domain
        turn_ip = "127.0.0.1"

    def reset_rule_replace(self, cfg: Configs):
        pass


def get_dns_manager():
    return DNSManager()


if __name__ == "__main__":
    manager = get_dns_manager()
    domain = "zone.huoying.qq.com"
