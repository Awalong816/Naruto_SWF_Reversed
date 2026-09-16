import logging
import queue
import select
import struct
import socket
import threading as th

from config import Configs

logging.basicConfig(level=logging.INFO)

class Socks5Manager:
    def __init__(
            self,
            host: str,
            port: int,
            max_input: int,
            t_host_domain: str | list[str] = None,
            t_host_ipv4: str | list[str] = None,
            t_host_ipv6: str | list[str] = None,
            ):
        # 基础
        self.server_host = host
        self.server_port = port
        self.stop = True # 循环开关

        # 前序分析可能ip，作为白名单
        if type(t_host_domain) is str:
            self.host_domain_white_list = [t_host_domain]
        elif t_host_domain is None:
            self.host_domain_white_list = []
        else:
            self.host_domain_white_list = t_host_domain

        if type(t_host_ipv4) is str:
            self.host_ipv4_white_list = [t_host_ipv4]
        elif t_host_ipv4 is None:
            self.host_ipv4_white_list = []
        else:
            self.host_ipv4_white_list = t_host_ipv4

        if type(t_host_ipv6) is str:
            self.host_ipv6_white_list = [t_host_ipv6]
        elif t_host_ipv6 is None:
            self.host_ipv6_white_list = []
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
        else:
            self.stop = False

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
        server.listen(self.max_input_queue)  # 设置最长等待队列，后面请求的会被拒绝 性质：建立好的通道数，在连接之后负责通信，本体基本不变化，所以上限值不大
        server.settimeout(1)  # 防止循环卡死 读取不到tcp也可以回到循环开头判断服务是不是还在进行，否则无法关闭循环
        # ========= 配置完成，放入线程运行 =========
        self.socket_handle = server
        self.socket_thread_handle = th.Thread( # 静止
            target=self._listening,  # 线程要执行的函数
            name="Socks5Server",  # 线程名字（方便调试）
            daemon=True,  # 守护线程, 随主线程结束而结束
        )
        logging.info(f"[INFO] ⬆️ Socks5 代理监听启动中...")
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
        target_pipe_client = None
        try:
            # 1.握手认证是socks5协议
            try:
                n = 2  # 第一位协议，第二位认证方式: 无认证，用户密码认证...
                result = self._recv_bytes(pipe_client, n)
                protocol, method_num = result[0], result[1]
                if protocol != 0x05:
                    raise TypeError(f"不是 socks5 协议")

                # 认证方法获取
                methods = self._recv_bytes(pipe_client, method_num)
                if 0x00 not in methods:
                    pipe_client.sendall(b'\x05\xff')  # 拒绝握手
                    raise PermissionError(f"没有无认证方法")

                # 选择认证方式
                pipe_client.sendall(b'\x05\x00')  # 选择除了无验证的其他方式需要等待客户端再发送内容，如用户名和密码 选择0则直接握手成功
            except Exception as err:
                logging.warning(f"[WARN] tcp socket 通道-握手失败: {err}")
                return

            # 2.获取目标信息
            try:
                n = 4
                protocol, command, signature, ip_type = self._recv_bytes(pipe_client, n)
                logging.info(
                    f"[SOCKS5] 收到命令: "
                    f"command={command}, ip_type={ip_type}"
                )
                if protocol != 0x05:
                    raise Exception(f"不是socks5协议")
                if command == 3:
                    # REP=0x07：Command not supported
                    self._handle_udp_associate(pipe_client)
                    return
                if command != 1:
                    """
                    01: CONNECT 建立tcp链接
                    02: BIND 绑定监听端口
                    03: UDP ASSOCIATE 建立udp转发通道
                    """
                    raise Exception(f"不支持的命令: {command}")
                if signature != 0:
                    raise Exception(f"预留位异常")
                # target host
                """
                * ip_type
                01: ipv4 地址
                03: 域名
                04: ipv6 地址
                """
                target_host = ""
                if ip_type == 1:  # ipv4
                    data = self._recv_bytes(pipe_client, 4)
                    ipv4 = socket.inet_ntop(socket.AF_INET, data)  # bytes -> str 默认的大端
                    if len(self.host_ipv4_white_list) > 0:
                        if ipv4 in self.host_ipv4_white_list:
                            target_host = ipv4
                    else:
                        target_host = ipv4
                elif ip_type == 3:  # domain
                    length = self._recv_bytes(pipe_client, 1)[0]  # **bytes索引是数值，切片还是bytes**
                    if length <= 0:
                        raise Exception(f"目标域名长度解析错误")
                    data = self._recv_bytes(pipe_client, length)
                    domain = data.decode("idna")
                    if len(self.host_domain_white_list) > 0:
                        if domain in self.host_domain_white_list:
                            target_host = domain
                    else:
                        target_host = domain
                elif ip_type == 4:  # ipv6
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
                logging.info(
                    f"[SOCKS5] 请求连接: "
                    f"{target_host}:{target_port}"
                )
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

            # 4.双向转发
            self._communication(
                src_pipe=pipe_client,
                tag_pipe=target_pipe_client,
                context=context,
            )
        except Exception as err:
            logging.warning(f"{err}")
        # 链接失效后关闭通道
        finally:
            if pipe_client:
                self._shutdown_socket(pipe_client)
            if target_pipe_client:
                self._shutdown_socket(target_pipe_client)

    def _recv_bytes(self, pipe: socket.socket, length: int):
        result = bytearray() # 可以序列化解包
        while len(result) < length:
            data = pipe.recv(length - len(result))
            if not data:
                raise ConnectionError(f"连接提前关闭")
            result.extend(data)
        return result

    def _shutdown_socket(self, pipe: socket.socket):
        # 删除追踪
        with self.socket_lock:
            self.pipe_clients.discard(pipe)
        # 关闭
        try:
            pipe.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            pipe.close()
        except OSError:
            pass

    def _communication( # 一条连接链
            self,
            src_pipe: socket.socket,
            tag_pipe: socket.socket,
            context: dict=None,
        ):
        sockets = [src_pipe, tag_pipe]

        while not self.is_stop():
            # 有可读的内容socket立即返回， 有可写的socket立即返回， 有错误的socket立即返回
            # **有readable就是发生了事件，需要处理(触发); writeable只是判断这个socket是否已满还能不能写入数据(常驻)**
            readable, writeable, wrongs = select.select(
                sockets, # 对应可读监控列表
                [], # 对应可写监控列表，基本都不为空，忽略
                sockets, # 对应错误的监控列表
                1, # 等不到抉择时间
            )
            # 有任何断裂就结束
            if wrongs:
                return

            if readable: # 触发了事件后
                for sock in readable:
                    event_data = sock.recv(65536) # 触发了事件后，不完整没关系，本身有可能是分块的
                    if not event_data: # 得到空等于一段关闭了连接，正常一直阻塞
                        if sock is src_pipe:
                            logging.warning(f"[WARN] 游戏客户端与代理层断开连接")
                        elif sock is tag_pipe:
                            logging.warning(f"[WARN] 代理层与游戏服务器断开连接")
                        return
                    else:
                        if sock is src_pipe:
                            direction = "game->server"
                            aim = tag_pipe
                        elif sock is tag_pipe:
                            direction = "server->game"
                            aim = src_pipe
                        else:
                            continue

                        aim.sendall(event_data)

    def close(self):
        logging.info(f"[INFO] Socks5 监听服务正在停止...")
        # 退出所有循环
        self.stop = True
        # 删除所有已追踪通道并关闭
        with self.socket_lock:
            for pipe_client in self.pipe_clients:
                try:
                    pipe_client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    pipe_client.close()
                except OSError:
                    pass

            self.pipe_clients.clear()

        if self.socket_handle: # 关闭在端口的监听，停止accept()阻塞
            self.socket_handle.close()

        # 关闭线程
        if self.socket_thread_handle and self.socket_thread_handle.is_alive():
            # 4. 等待监听线程自行结束
            thread = self.socket_thread_handle
            thread.join(timeout=3)

            if thread.is_alive():
                logging.warning(
                    "[WARN] SOCKS5监听线程未按时退出"
                )

        self.socket_handle = None
        self.socket_thread_handle = None
        logging.info(f"[INFO] Socks5 服务已关闭")

    def _handle_udp_associate(self, pipe_client):
        udp_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )
        udp_socket.bind(("127.0.0.1", 0))

        bind_host, bind_port = udp_socket.getsockname()

        # REP=0：UDP ASSOCIATE建立成功
        pipe_client.sendall(
            b"\x05\x00\x00\x01"
            + socket.inet_aton(bind_host)
            + struct.pack("!H", bind_port)
        )

        logging.info(
            f"[SOCKS5] UDP占位通道: "
            f"{bind_host}:{bind_port}"
        )

        try:
            # SOCKS5规定：TCP控制连接存在期间，UDP关联才有效
            while not self.stop:
                readable, _, _ = select.select(
                    [pipe_client],
                    [],
                    [],
                    1,
                )

                if pipe_client in readable:
                    if not pipe_client.recv(1):
                        break
        finally:
            udp_socket.close()


def get_socks_manager(cfg: Configs):
    host = cfg.net_proxy_host or "127.0.0.1"
    port = int(cfg.net_proxy_prot or 19080)
    max_input_events = int(cfg.net_proxy_max_input_queue)

    return Socks5Manager(
        host=host,
        port=port,
        max_input=max_input_events,
        t_host_domain=cfg.send_server_domain,
        t_host_ipv4=cfg.send_server_ips
    )


if __name__ == "__main__":
    cfgs = Configs()
    cfgs.initialization_configs(r"E:\pythonProject\启动器\config.yaml")
    cfgs.send_server_ips = ["101.226.142.64"]

    socks5_manager = get_socks_manager(cfgs)
    socks5_manager.start()
    input(f"socks5 任意输入结束:")
    socks5_manager.close()

