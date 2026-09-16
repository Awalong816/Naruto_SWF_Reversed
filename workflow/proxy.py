import logging

from config import Configs
from net import NetClient, ProxyManager


def proxy_start(cfg: Configs, net_client: NetClient):
    """
    启动本地代理
    :param net_client: 全局网络客户端
    :param cfg: 运行配置
    :return:
    """
    debug = cfg.debug

    net_client.rig_socks5_manager(cfg)
    net_client.rig_proxy_manager(cfg)

    # 代理服务状态检察
    if not net_client.proxy_manager.check_proxy_bridge():
        exit(1)

    # 先启动 socks5 服务
    net_client.socks5_manager.start()
    # 后启动 proxy 代理规则
    net_client.proxy_manager.start()






