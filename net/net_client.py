import sys
import os
import httpx
import logging
from pathlib import Path
from typing import Optional

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import Configs
from .dns_util.dns_manager import get_dns_manager, DNSManager
from .socks5_manager.socks5_manager import get_socks_manager, Socks5Manager
from .proxy_manager.proxy_manager import get_proxy_manager, ProxyManager

logging.basicConfig(level=logging.INFO) # 最低播报等级


class NetClient:
    def __init__(self, max_connection=50, timeout=60):
        self.client = httpx.Client(
            limits=httpx.Limits(
                max_keepalive_connections=max_connection,
                max_connections=max_connection,
            ),
            timeout=timeout,
            http2=True,
            follow_redirects=True, # 允许重定向
        )
        self.dns_manager = get_dns_manager() # dns模块
        self.socks5_manager: Optional[Socks5Manager] = None
        self.proxy_manager: Optional[ProxyManager] = None

    def get(self, url: str, **kwargs):
        response = self.client.get(url, **kwargs)
        if response.is_success:
            data = response.content
            return data
        else:
            if not response.is_redirect:
                raise Exception(f"请求资源 <{url}> 失败\n状态码: {response.status_code}\n说明: {response.text}")

    def download_requirement(self, requirement: dict, save_path: str):
        save_dir = Path(save_path)
        if not save_dir.is_dir():
            raise Exception(f"保存路径 <{save_path}> 不是有效目录")

        for file_name, url in requirement.items():
            try:
                file_data = self.get(url)
                file_path = save_dir / file_name  # 路径拼接

                # 确保父目录存在
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # 写入文件
                file_path.write_bytes(file_data)

            except Exception as err:
                logging.warning(f"[WARN] {err}")
                continue

    def rig_socks5_manager(self, cfg: Configs):
        self.socks5_manager = get_socks_manager(cfg)

    def rig_proxy_manager(self, cfg: Configs):
        self.proxy_manager = get_proxy_manager(cfg)

    def close(self):
        if self.socks5_manager:
            self.socks5_manager.close()

        if self.proxy_manager:
            self.proxy_manager.close()

def get_net_client(cfg: Configs):
    return NetClient(cfg.net_max_connection, cfg.net_timeout)