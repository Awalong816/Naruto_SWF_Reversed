import os
import logging
import ctypes

from config import Configs
from workflow import get_qqgamebox_client_path, analyze_from_server, analyze_tbs_cache_front, proxy_start
from net import get_net_client

logging.basicConfig(level=logging.INFO) # 最低播报等级


def is_admin(debug=False):
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception as err:
        if debug:
            print(f"管理员权限无法判断: {err}")
        return False

socket_flow = """
1. 快捷方式启动 Launch.exe
   参数：/appid:1103286479
        ↓
2. Launch.exe 查找当前版本目录
   例如：4.1.4.1
        ↓
3. 启动 QQMicroGameBox.exe
        ↓
4. 读取 data/1103286479/Config.ini
   得到登录页面、GameID、Flash配置
        ↓
5. WebBrowserProcess.exe 打开腾讯登录页面
        ↓
6. 登录完成，进入 minigame app_frame
   appid=10190
        ↓
7. 打开火影QQGame登录页面
        ↓
8. 玩家选择区服，例如 zone_id=541
        ↓
9. 网页请求 query_svr_info.fcgi
   查询541区服务器
        ↓
10. 返回服务器信息
    zone.huoying.qq.com
    port=10494
    res.huoying.qq.com
    version.js
        ↓
11. 请求 version.js
    得到当前版本 NarutoBeta11.xxBuildxxx
        ↓
12. 网页拼出完整entry地址
    entry.swf?zone_id=541
             &ip=zone.huoying.qq.com
             &port=10494
             &host=https://res.huoying.qq.com
        ↓
13. WebBrowserProcess中的Pepper Flash加载entry.swf
        ↓
14. entry.swf读取loaderInfo.parameters
        ↓
15. 参数写入ApplicationData
    ip   = zone.huoying.qq.com
    port = 10494
        ↓
16. 加载resource.cfg、core、include、server等组件
        ↓
17. NarutoServer插件初始化
        ↓
18. 请求Flash Policy
    远程端口8001/10494
        ↓
19. SocketServer调用Socket.connect()
        ↓
20. WebBrowserProcess使用自己的解析路径
    把域名转换成官方IP
        ↓
21. Windows分配随机本地端口
    本地63644 → 官方101.91.33.201:10494
        ↓
22. 建立TCP连接
        ↓
23. 编码Protobuf消息
    必要时TEA加密
        ↓
24. writeBytes() + flush()
    数据发送到官方服务器
"""


if __name__ == "__main__":
    # url的关系:
    # game.huoying.qq.com: 负责登录录入信息页面，查询区服信息，返回游戏该从哪里进行通信和版本文件 ↓ 大门
    # zone.huoying.qq.com: 游戏业务服务器， 用于登录角色，收发游戏指令，数据 *关键* 师傅
    # res.huoying.qq.com: 静态资源服务器，提下载地址 ↑ 工具箱

    # 初始化全局配置
    global_config = Configs()
    global_config.initialization_configs()

    global_net_client = get_net_client(global_config)
    # 鉴权
    if not is_admin(global_config.debug):
        logging.error(f"[ERROR] 鉴权失败, 使用管理员身份重新打开")
        exit(1)

    # ======= 1.1 先主动获取资源和服务器信息 =======
    try:
        resource_requirement = analyze_from_server(global_config, global_net_client)
    except Exception as err:
        # 1.2 失败后从本地获取
        logging.warning(f"[WARN] {err}\n转为本地缓存文件获取...")
        # 获取游戏本体本地目录
        try:
            essence_dir = get_qqgamebox_client_path()
        except NotADirectoryError as err:
            logging.error(f"[ERROR] {err}")
            exit(1)
        except Exception as err:
            logging.error(f"[ERROR] 获取游戏目录路径失败: {err}")
            exit(1)

        # 分析本地tbs缓存得到前置资源
        try:
            tbs_cache_path = os.path.join(essence_dir, "tbs_cache")
            resource_requirement_font = analyze_tbs_cache_front(tbs_cache_path, global_config)
        except Exception as err:
            logging.error(f"[ERROR] 获取前置资源url表单失败: {err}")
            exit(1)

        # ======= 项目更新用 ========

        # 下载前置资源
        # try:
        #     global_net_client.download_requirement(resource_requirement_font, global_config.resource_save_path)
        #     logging.info(f"[INFO] 前置资源获取成功, 保存目录: {global_config.resource_save_path}")
        # except Exception as err:
        #     logging.error(f"[ERROR] 获取前置资源文件失败: {err}")
        #     exit(1)

        #  处理后置资源
        #  ✅ 创建生成器（不会执行任何代码）
        # gen = analyze_tbs_cache_after(global_config)
        #
        #  ✅ 第一次 next() → 执行到 yield，返回 resource_requirement
        # try:
        #     resource_requirement_after = next(gen)
        # except StopIteration:
        #     logging.error("[ERROR] 生成器没有返回资源需求")
        #     exit(1)
        # except Exception as err:
        #     logging.error(f"[ERROR] 后置资源处理错误: {err}")
        #     exit(1)

        #  ✅ 下载后置资源
        # try:
        #     global_net_client.download_requirement(resource_requirement_after, global_config.resource_save_path)
        #     logging.info(f"[INFO] 后置资源下载成功")
        # except Exception as err:
        #     logging.error(f"[ERROR] 获取后置资源文件失败: {err}")
        #     exit(1)
        #
        #  ✅ 第二次 next() → 继续执行 part2（解密）
        # try:
        #     next(gen)
        #     logging.info("[INFO] 解密完成")
        # except StopIteration:
        #     # 生成器正常结束
        #     pass
        # except Exception as err:
        #     logging.error(f"[ERROR] 解密失败: {err}")
        #     exit(1)
        #
        # resource_requirement = resource_requirement_font | resource_requirement_after

    # ======= 2.开始代理 ========

    try:
        proxy_start(global_config, global_net_client)
    except Exception as err:
        logging.error(f"[ERROR] 启动本地代理失败: {err}")
        exit(1)

    # 最后检查
    if global_config.send_server_domain and global_config.send_server_prot >= 0 and len(global_config.send_server_ips) > 0:
        logging.info(f"[INFO] 找到游戏服务器域名: {global_config.send_server_domain}")
        logging.info(f"[INFO] 找到游戏服务器接收端口: {global_config.send_server_prot}")
        logging.info(f"[INFO] 得出游戏服务器域名挂载IP组: {global_config.send_server_ips}")
    else:
        logging.error(f"[ERROR] 前置条件缺失,无法继续运行")
        exit(1)


