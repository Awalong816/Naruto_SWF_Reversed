import os
import logging

from config import Configs
from workflow import get_qqgamebox_client_path, analyze_tbs_cache_front, analyze_tbs_cache_after
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
        tbs_cache_path = os.path.join(essence_dir, "tbs_cache")
        resource_requirement_font = analyze_tbs_cache_front(tbs_cache_path, global_config)
    except Exception as err:
        logging.error(f"[ERROR] 获取前置资源url表单失败: {err}")
        exit(1)

    # 下载前置资源
    try:
        global_net_client.download_requirement(resource_requirement_font, global_config.resource_save_path)
        logging.info(f"[INFO] 前置资源获取成功, 保存目录: {global_config.resource_save_path}")
    except Exception as err:
        logging.error(f"[ERROR] 获取前置资源文件失败: {err}")
        exit(1)

    # ======= 项目更新用 ========

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
