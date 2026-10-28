import logging
import socket
import random

from config import Configs
from net import NetClient, ProxyManager
from frontend import get_frontend


def _bind_test(cfg: Configs, port: int):
    """
    端口探针
    """
    if cfg.os_type == "windows":
        host = cfg.net_proxy_host or "127.0.0.1"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # 创建实例
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows 必须用这个
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1) # 设置实例为独占模式
            s.bind((host, port))  # 尝试绑定
            s.listen(1) # 测试是否成功
            return True
        except OSError:
            return False
        finally:
            s.close()
    else:
        raise TypeError(f"系统:{cfg.os_type} 不支持启用 'random' 端口")


def proxy_start(cfg: Configs, net_client: NetClient):
    """
    启动本地代理
    :param net_client: 全局网络客户端
    :param cfg: 运行配置
    :return:
    """
    debug = cfg.debug

    if isinstance(cfg.net_proxy_port, str) and cfg.net_proxy_port.lower() == "random":
        passed = False
        n = 0
        try:
            while not passed:
                n += 1
                port = random.randint(10000, 65535)
                if _bind_test(cfg, port):
                    cfg.net_proxy_port = port
                    passed = True
                else:
                    if n >= 50:
                        raise TimeoutError(f"无法获得有效代理端口")
        except Exception as err:
            raise err

    net_client.rig_socks5_manager(cfg)
    net_client.rig_proxy_manager(cfg)

    # 代理服务状态检察
    if not net_client.proxy_manager.check_proxy_bridge():
        exit(1)

    # 启用前端
    # proxy 管理器装配完成后、socks5 服务启动之前：创建前端
    frontend = get_frontend(
        socks5_manager=net_client.socks5_manager,
        on_close=lambda: net_client.close(),
        poll_ms=400,
    )

    # 先启动 socks5 服务
    net_client.socks5_manager.start()
    # 后启动 proxy 代理规则
    net_client.proxy_manager.start()

    return frontend






