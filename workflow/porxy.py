import logging

from config import Configs
from utils import get_dns_manager

dns_manager = get_dns_manager()


def save_real_ips(cfg: Configs):
    server_ips = dns_manager.domain2ip(cfg.send_server_domain)
    cfg.send_server_ips = server_ips


def proxy_start(cfg: Configs):
    """
    启动本地代理
    :param cfg: 运行配置
    :return:
    """
    try:
        save_real_ips(cfg)
        logging.info(f"[INFO] 得到域名挂载ip组: {cfg.send_server_ips}")
    except Exception as err:
        raise f"保存域名ip组失败: {err}"

