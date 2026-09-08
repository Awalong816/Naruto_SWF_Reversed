import logging

from config import Configs
from net.net_client import NetClient


def save_real_ips(cfg: Configs, net_client: NetClient):
    server_ips = net_client.dns_manager.domain2ip(cfg.send_server_domain)
    cfg.send_server_ips = server_ips


def proxy_start(cfg: Configs, net_client: NetClient):
    """
    启动本地代理
    :param net_client: 全局网络客户端
    :param cfg: 运行配置
    :return:
    """
    debug = cfg.debug

    # 兜底
    try:
        save_real_ips(cfg, net_client)
        logging.info(f"[INFO] 得到域名挂载ip组: {cfg.send_server_ips}")
    except Exception as err:
        logging.warning(f"[WARN] 保存域名ip组失败: {err}")

