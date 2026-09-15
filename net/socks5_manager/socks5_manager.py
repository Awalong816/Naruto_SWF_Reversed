import logging
import queue
import struct
import socket
import threading as th

from config import Configs

class Socks5Manager:
    def __init__(
            self,
            host: str,
            port: int,
            max_input: int,
            t_host_domain: str="" | list[str],
            t_host_ipv4: str="" | list[str],
            t_host_ipv6: str="" | list[str],
            ):
        # 基础
        self.server_host = host
        self.server_port = port
        self.stop = True # 循环开关

        # 前序分析可能ip，作为白名单
        if type(t_host_domain) is str:
            self.host_domain_white_list = [t_host_domain]
        else:
            self.host_domain_white_list = t_host_domain

        if type(t_host_ipv4) is str:
            self.host_ipv4_white_list = [t_host_ipv4]
        else:
            self.host_ipv4_white_list = t_host_ipv4

        if type(t_host_ipv6) is str:
            self.host_ipv6_white_list = [t_host_ipv6]
        else:
            self.host_ipv6_white_list = t_host_ipv6

        # 句柄
        self.socket_handle = None # socket句柄
        self.socket_thread_handle = None # 运行socket循环的线程的句柄
        # 子项
        self.socket_lock = th.Lock() # 线程锁
        self.pipe_clients = set() # 自动快速去重

        # 传递给gui的事件
        self.max_input_queue = max_input

    def is_stop(self):
        return self.stop

    def start(self):
        """
        socket 本质是一个事件循环
        两层线程
        - socket 监听循环线程 一个
        - tcp 事件处理线程 n个
        """
        # 已经启动
        if not self.is_stop():
            return

        # ========= 配置socket =========
        # 创建socket类
        # 快递站属性: 只收tcp包
        server = socket.socket(
            socket.AF_INET,  # ipv4
            socket.SOCK_STREAM,  # tcp类型
        )
        # 设置端口通道复用 (频繁开关不等待) sockopt--套接字选项
        # 快递站运行方式，与tcp包无关
        server.setsockopt(
            socket.SOL_SOCKET,  # socket层， 分为套接字层，ip层，tcp层 每个对应的功能不同
            socket.SO_REUSEADDR,  # 允许重复使用 本地地址
            1
        )
        server.bind((self.server_host, self.server_port))  # socket绑定
        # 循环accept()会阻塞等待到读取tcp
        server.listen(self.max_input_queue)  # 设置最长等待队列，后面请求的会被拒绝
        server.settimeout(1)  # 防止循环卡死 读取不到tcp也可以回到循环开头判断服务是不是还在进行，否则无法关闭循环
        # ========= 配置完成，放入线程运行 =========
        self.socket_handle = server
        self.socket_thread_handle = th.Thread( # 静止
            target=self._listening,  # 线程要执行的函数
            name="Socks5Server",  # 线程名字（方便调试）
            daemon=True,  # 守护线程, 随主线程结束而结束
        )
        self.socket_thread_handle.start()

    def _listening(self):
        """
        一级线程 监听事件循环，分发二级线程
        server: socket 是监听模式 listening listen()设置
        client: socket 是连接模式 established
        """
        while not self.stop:
            try:
                # 阻塞
                # 返回的是一条 tcp socket 字节流的通道，和来源信息
                pipe_client, pipe_info = self.socket_handle.accept()
            except socket.timeout as timeout: # 正常空置
                continue # 如果服务关闭了从这里返回
            except OSError as err:
                logging.error(f"[ERROR] socket 循环遇到系统错误: {err}")
                break
            # 拿到tcp事件后 推进到这里 上锁添加事件
            with self.socket_lock: # with 本质是占用，其他进程无法获得，locked()是查询状态，与二级线程对应
                self.pipe_clients.add(pipe_client) # tcp socket通道句柄记录
            # 创建二层线程分发处理，不阻塞继续接线
            th.Thread(
                target=self._dealing,
                args=(pipe_client, pipe_info),
                name=f"pipe evnet belong: <{pipe_info[0]}:{pipe_info[1]}>",
                daemon=True,  # 守护线程
            ).start()

    def _dealing(
            self,
            pipe_client: socket.socket,
            pipe_info,
            ):
        """
        二级线程 处理tcp交互事件
        * 每一环节都有独立的头 第一位都是协议版本
        1. socks5 握手
        2. 连接目标
        3. 双向转发
        """
        # 1.握手认证是socks5协议
        try:
            n = 2 # 第一位协议，第二位认证方式: 无认证，用户密码认证...
            result = self._recv_bytes(pipe_client, n)
            protocol, method_num = result[0], result[1]
            if protocol != 0x05:
                raise TypeError(f"不是 socks5 协议")

            # 认证方法获取
            methods = self._recv_bytes(pipe_client, method_num)
            if 0x00 not in methods:
                pipe_client.sendall(b'\x05\xff') # 拒绝握手
                raise PermissionError(f"没有无认证方法")

            # 选择认证方式
            pipe_client.sendall(b'\x05\x00') # 选择除了无验证的其他方式需要等待客户端再发送内容，如用户名和密码 选择0则直接握手成功
        except Exception as err:
            logging.warning(f"[WARN] tcp socket 通道-握手失败: {err}")
            return

        # 2.获取目标信息
        try:
            n = 4
            protocol, command, signature, ip_type = self._recv_bytes(pipe_client, n)
            if protocol != 0x05:
                raise Exception(f"不是socks5协议")
            if command != 0x01:
                """
                01: CONNECT 建立tcp链接
                02: BIND 绑定监听端口
                03: UDP ASSOCIATE 建立udp转发通道
                """
                raise Exception(f"不支持的命令: {command}")
            if signature != 0x00:
                raise Exception(f"预留位异常")
            # target host
            """
            * ip_type
            01: ipv4 地址
            03: 域名
            04: ipv6 地址
            """
            target_host = ""
            if ip_type == b'\x01': # ipv4
                data = self._recv_bytes(pipe_client, 4)
                ipv4 = socket.inet_ntop(socket.AF_INET, data) # bytes -> str 默认的大端
                if len(self.host_ipv4_white_list) > 0:
                    if ipv4 in self.host_ipv4_white_list:
                        target_host = ipv4
                else:
                    target_host = ipv4
            elif ip_type == b'\x03': # domain
                length = self._recv_bytes(pipe_client, 1)[0] # **bytes索引是数值，切片还是bytes**
                if length <= 0:
                    raise Exception(f"目标域名长度解析错误")
                data = self._recv_bytes(pipe_client, length)
                domain = data.decode("idna")
                if len(self.host_domain_white_list) > 0:
                    if domain in self.host_domain_white_list:
                        target_host = domain
                else:
                    target_host = domain
            elif ip_type == b'\x04': # ipv6
                data = self._recv_bytes(pipe_client, 16)
                ipv6 = socket.inet_ntop(socket.AF_INET6, data)
                if len(self.host_ipv6_white_list) > 0:
                    if ipv6 in self.host_ipv6_white_list:
                        target_host = ipv6
                else:
                    target_host = ipv6
            else:
                raise Exception(f"不支持的host请求")
            # target port SOCKS5规定大端在前 高位在前
            target_port = struct.unpack("!H", self._recv_bytes(pipe_client, 2))[0]
            # 组成连接的上下文
            context = {
                "src_host": pipe_info[0],
                "src_port": pipe_info[1],
                "tag_host": target_host,
                "tag_port": target_port,
            }
        except Exception as err:
            logging.warning(f"[WARN] tcp socket 通道-获取目标失败: {err}")
            return

        # 3.连接目标服务器
        try:
            target_pipe_client = socket.create_connection(
                (target_host, target_port),
                timeout=30,
            )
            target_pipe_client.settimeout(None)
            self.pipe_clients.add(target_pipe_client)
            pipe_client.sendall(
                b"\x05\x00\x00\x01"  # socks5版本，状态，标志位，host类型
                b"\x00\x00\x00\x00"  # 绑定地址 不关心凑最小长度用
                b"\x00\x00"  # 绑定端口 凑最小长度用
            )
        except Exception as err:
            logging.warning(f"[WARN] tcp socket 通道-连接目标服务器失败: {err}")
            return

    def _recv_bytes(self, pipe: socket.socket, length: int):
        result = bytearray() # 可以序列化解包
        while len(result) < length:
            data = pipe.recv(length - len(result))
            if not data:
                raise ConnectionError(f"连接提前关闭")
            result.extend(data)
        return result


def get_socks_manager(cfg: Configs):
    host = cfg.net_proxy_host or "127.0.0.1"
    port = int(cfg.net_proxy_prot or 19080)

    return Socks5Manager(host, port, )


if __name__ == "__main__":
    cfgs = Configs()
    cfgs.initialization_configs(r"../config.yaml")

    socks5_manager = get_socks_manager()
