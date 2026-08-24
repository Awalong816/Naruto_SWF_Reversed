import logging

from config import Configs
from utils import get_qqgamebox_client_path, analyze_tbs_cache_front
from net import get_net_client

logging.basicConfig(level=logging.INFO) # 最低播报等级

if __name__ == "__main__":
    # 初始化全局配置
    global_config = Configs()
    global_config.initialization_configs()

    global_net_client = get_net_client(global_config)

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
        resource_requirement = analyze_tbs_cache_front(essence_dir, global_config)
    except Exception as err:
        logging.error(f"[ERROR] 获取前置资源url表单失败: {err}")
        exit(1)

    # 下载前置资源
    try:
        global_net_client.download_requirement(resource_requirement, global_config.resource_save_path)
        logging.info(f"[INFO] 前置资源获取成功, 保存目录: {global_config.resource_save_path}")
    except Exception as err:
        logging.error(f"[ERROR] 获取前置资源文件失败: {err}")
        exit(1)
