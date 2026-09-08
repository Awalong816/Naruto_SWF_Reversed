import subprocess as sub # 指令运行
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

class ProxyManager:
    def __init__(self):
        pass

    def check_proxy_bridge(self, os_type="windows") -> bool:
        if os_type == "windows":
            try:
                result = sub.run(['where', 'ProxyBridge_CLI.exe'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    logging.warning("[WARN] proxy-bridge 未安装")
                elif result.returncode == 0 and result.stdout:
                    logging.info("[INFO] proxy-bridge 已安装")
                    return True
            except Exception as err:
                logging.error(f"[ERROR] proxy-bridge 检查失败: {err}")
        elif os_type == "mac" or os_type.lower() == "macos":
            try:
                app_paths = [
                    Path("/Applications/ProxyBridge.app"),
                    Path.home() / "Applications/ProxyBridge.app",
                    Path("/opt/homebrew/Caskroom/proxybridge"),  # Homebrew 安装位置
                ]
                for app_path in app_paths:
                    if app_path.exists():
                        logging.info(f"[INFO] proxy-bridge 已安装")
                        return True
                logging.warning(f"[WARN] 暂不提供mac系统自动下载, 需要手动安装 proxy-bridge")
                logging.error(f"[ERROR] proxy-bridge 未安装")
            except Exception as err:
                logging.error(f"[ERROR] proxy-bridge 检查失败: {err}")
        else:
            logging.error(f"[ERROR]不支持代理系统: {os_type}")

        return False


if __name__ == "__main__":
    os_type = "mac"
    proxy_manager = ProxyManager()
    proxy_manager.check_proxy_bridge(os_type)