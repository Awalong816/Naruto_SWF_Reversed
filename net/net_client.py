import sys
import os
import httpx
import logging
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import Configs

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

    def _get(self, url: str, **kwargs):
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
                file_data = self._get(url)
                file_path = save_dir / file_name  # 路径拼接

                # 确保父目录存在
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # 写入文件
                file_path.write_bytes(file_data)

            except Exception as err:
                logging.warning(f"[WARN] {err}")
                continue


def get_net_client(cfg: Configs):
    return NetClient(cfg.net_max_connection, cfg.net_timeout)