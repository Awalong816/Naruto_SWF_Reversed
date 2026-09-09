import subprocess as sub
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)


class ProxyManager:
    def __init__(self):
        self.proxy_bridge_path = None

    def check_proxy_bridge(self, os_type="windows") -> bool:
        """检查并安装 ProxyBridge"""
        if os_type in ["windows", "win"]:
            return self._check_windows()
        elif os_type in ["mac", "macos", "darwin"]:
            return self._check_macos()
        else:
            logging.error(f"[ERROR] 不支持的系统: {os_type}")
            return False

    def _check_windows(self) -> bool:
        """Windows 检查"""
        # 1. 快速检查是否已安装
        if not self._is_installed_windows():
            if not self._install_windows():
                return False

        # 2. 查找 CLI 路径
        cli_path = self._find_cli_windows()
        if not cli_path:
            logging.error("[ERROR] 找不到 ProxyBridge_CLI.exe")
            return False

        # 3. 验证可用性
        if not self._verify_cli(cli_path):
            return False

        self.proxy_bridge_path = cli_path
        logging.info(f"[INFO] ✅ ProxyBridge 就绪: {cli_path}")
        return True

    def _is_installed_windows(self) -> bool:
        """检查是否已安装"""
        result = sub.run(
            ['winget', 'list', '--id', 'InterceptSuite.ProxyBridge', '--exact'],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='ignore'
        )
        return result.returncode == 0

    def _install_windows(self) -> bool:
        """安装 ProxyBridge"""
        logging.warning("[WARN] ProxyBridge 未安装")
        ans = input("是否自动安装? (y/n): ").strip().lower()

        if ans != 'y':
            logging.info("跳过安装")
            return False

        logging.info("正在安装...")
        result = sub.run(
            ['winget', 'install', '--id', 'InterceptSuite.ProxyBridge',
             '--exact', '--silent', '--accept-package-agreements'],
            capture_output=True,
            text=True,
            timeout=300,
            encoding='utf-8',
            errors='ignore'
        )

        if result.returncode == 0:
            logging.info("[INFO] ✅ 安装成功")
            return True
        else:
            logging.error(f"[ERROR] 安装失败: {result.stderr}")
            return False

    def _find_cli_windows(self):
        """查找 CLI 路径"""
        # 方法1: 在 PATH 中查找
        cli_path = shutil.which("ProxyBridge_CLI.exe")
        if cli_path:
            return Path(cli_path)

        # 方法2: 检查常见安装位置
        common_paths = [
            Path(r"C:\Program Files\ProxyBridge\ProxyBridge_CLI.exe"),
            Path(r"C:\Program Files (x86)\ProxyBridge\ProxyBridge_CLI.exe"),
        ]

        for path in common_paths:
            if path.is_file():
                return path

        return None

    def _verify_cli(self, cli_path: Path) -> bool:
        """验证 CLI 可用性"""
        # 检查依赖文件
        dll_path = cli_path.parent / "ProxyBridgeCore.dll"
        if not dll_path.is_file():
            logging.error(f"[ERROR] 缺少 ProxyBridgeCore.dll")
            return False

        # 运行版本检查
        try:
            result = sub.run(
                [str(cli_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logging.info(f"[INFO] 版本: {result.stdout.strip() or '未知'}")
                return True
            else:
                logging.error(f"[ERROR] 运行异常: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"[ERROR] 启动检查失败: {e}")
            return False

    def _check_macos(self) -> bool:
        """macOS 检查"""
        # 检查常见安装路径
        app_paths = [
            Path("/Applications/ProxyBridge.app"),
            Path.home() / "Applications/ProxyBridge.app",
        ]

        for path in app_paths:
            if path.exists():
                logging.info(f"[INFO] ✅ ProxyBridge 已安装: {path}")
                # 尝试查找 CLI
                cli_path = path / "Contents/MacOS/proxybridge-cli"
                if cli_path.exists():
                    self.proxy_bridge_path = str(cli_path)
                return True

        logging.warning("[WARN] ProxyBridge 未安装")
        logging.info("[INFO] 请手动安装: brew install --cask proxybridge")
        return False


if __name__ == "__main__":
    os_type = "windows"
    pm = ProxyManager()
    pm.check_proxy_bridge(os_type)