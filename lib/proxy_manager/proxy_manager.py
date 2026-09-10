import signal
import subprocess as sub # 指令运行
import os
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

class ProxyManager:
    def __init__(self, os_type: str):
        self.os_type = os_type
        self.proxy_bridge_path = ""
        self.proxy_handle = None

    def check_proxy_bridge(self) -> bool:
        # windows
        if self.os_type == "windows":
            try:
                # 位置
                result = sub.run(
                    ['winget', 'list', '--id', 'InterceptSuite.ProxyBridge', '--exact'],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding='utf-8',
                    errors='ignore'
                )
                if result.returncode != 0:
                    logging.warning("[WARN] proxy-bridge 未安装")
                    install_ans = input("是否由工作流自动安装`proxy-bridge`?(y/n):")
                    # print(type(install_ans))
                    if install_ans.lower() == "y":
                        logging.info("[INFO] 开始自动安装 proxy-bridge...")
                        result = sub.run(
                            [
                                'winget', 'install',
                                '--id', 'InterceptSuite.ProxyBridge',
                                '--exact',
                                '--accept-package-agreements',  # ✅ 自动接受包协议
                                '--accept-source-agreements',  # ✅ 自动接受源协议
                                '--silent'  # ✅ 静默安装（可选）
                            ],
                            capture_output=True,
                            text=True,
                            timeout=300,  # 增加到5分钟
                            encoding='utf-8',
                            errors='ignore'
                        )
                        if result.returncode == 0 and result.stdout:
                            logging.info("[INFO] proxy-bridge 安装成功")
                        else:
                            logging.error(f"[ERROR] proxy-bridge 安装失败: {result.stderr}")
                            return False
                    elif install_ans.lower() == "n":
                        return False
                    else:
                        raise ValueError("输入非法")
                elif result.returncode == 0 and result.stdout:
                    logging.info("[INFO] proxy-bridge 已安装")

                possible_paths = [
                    shutil.which("ProxyBridge_CLI.exe"),
                    Path(
                        os.environ.get("ProgramFiles", r"C:\Program Files")
                    ) / "ProxyBridge" / "ProxyBridge_CLI.exe",
                ]

                cli_path = None

                for path in possible_paths:
                    if path and Path(path).is_file():
                        cli_path = Path(path).resolve() # 绝对路径
                        break

                if cli_path is None:
                    logging.warning(
                        "[WARN] 找不到ProxyBridge_CLI.exe"
                    )
                    return False
            except Exception as err:
                logging.error(f"[ERROR] proxy-bridge 检查失败: {err}")
            # 检查可用性
            core_path = cli_path.parent / "ProxyBridgeCore.dll"

            if not core_path.is_file():
                logging.warning(
                    f"[WARN] 缺少ProxyBridgeCore.dll: {core_path}"
                )
                return False

            try:
                result = sub.run(
                    [str(cli_path), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    errors="ignore",
                )
            except Exception as err:
                logging.error(
                    f"[ERROR] ProxyBridge启动检查失败: {err}"
                )
                return False

            if result.returncode != 0:
                logging.error(
                    f"[ERROR] ProxyBridge运行异常:\n"
                    f"{result.stdout}\n{result.stderr}"
                )
                return False

            self.proxy_bridge_path = str(cli_path)

            version = result.stdout.strip() or "版本未知"

            logging.info(
                f"[INFO] ProxyBridge依赖正常\n"
                f"路径: {cli_path}\n"
                f"版本: {version}"
            )

            return True
        # mac
        elif self.os_type == "mac" or os_type.lower() == "macos":
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

    def start(self, cfg_path="./.pbprofile"):
        if self.os_type == "windows":
            if not self.proxy_bridge_path:
                logging.error("[ERROR] ProxyBridge 路径未设置，请先调用 check_proxy_bridge")
                return False
            cfg_file = Path(cfg_path)
            if not cfg_file.is_file():
                logging.error(f"[ERROR] ProxyBridge 配置文件不存在: {cfg_path}")
                return False

            try:
                # 启动 ProxyBridge CLI，加载配置文件
                # --verbose 2 表示输出连接事件日志
                cmd = [
                    self.proxy_bridge_path,
                    "--profile", str(cfg_file.resolve()),
                    "--verbose", "2"
                ]

                logging.info(f"[INFO] 启动 ProxyBridge: {' '.join(cmd)}")

                # 使用 Popen 后台启动，不阻塞当前进程
                self.proxy_handle = sub.Popen(
                    cmd,
                    stdout=sub.PIPE,
                    stderr=sub.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    # Windows 下创建新进程组，方便后续管理
                    creationflags=sub.CREATE_NEW_PROCESS_GROUP
                )

                logging.info("[INFO] ProxyBridge 已启动")
                return True

            except Exception as err:
                logging.error(f"[ERROR] 启动失败: {err}")
                return False

    def close(self):
        if self.os_type == "windows":
            if not self.proxy_handle:
                logging.warning("[WARN] 没有正在运行的 ProxyBridge 进程")
                return

            try:
                # 发送 Ctrl+C 信号，让程序优雅退出并清理规则
                self.proxy_handle.send_signal(signal.CTRL_C_EVENT)
                logging.info("[INFO] 已发送停止信号")

                # 等待进程退出
                self.proxy_handle.wait(timeout=5)
                logging.info("[INFO] ProxyBridge 已关闭")

            except sub.TimeoutExpired:
                # 超时未退出，强制终止
                logging.warning("[WARN] ProxyBridge 关闭超时，强制终止")
                self.proxy_handle.terminate()
                self.proxy_handle.wait(timeout=3)

            except Exception as err:
                logging.error(f"[ERROR] ProxyBridge 关闭失败: {err}")
            finally:
                self.proxy_handle = None


def get_proxy_manager(os_type: str="windows"):
    return ProxyManager(os_type)


if __name__ == "__main__":
    os_type = "windows"
    proxy_manager = ProxyManager(os_type)
    proxy_manager.check_proxy_bridge()