import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qs

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 现在可以直接导入
from config import Configs
from utils import get_decompress_manager, get_type_reader_manager, get_decrypt_manger

# 筛选url二进制字节段
# re.compile 包装成对象，使用search方法进行正则匹配
# https? http后面只跟0或1个s
# [...] 匹配其中任意一个字符
# `]` 需要转义成`\]`否则视为结束
# ]后的`+`表示匹配一个或多个
url_tpf = re.compile(
    rb"https?://[A-Za-z0-9._~:/?#[\]@!$&()*+,;=%-]+"
)

version_sign = re.compile(
    r"https://res\.huoying\.qq\.com/NarutoBeta(\d+)\.(\d+)Build(\d+)"
)

decompress_manager = get_decompress_manager()
type_reader_manager = get_type_reader_manager()
decrypt_manager = get_decrypt_manger()


def url_tpf_test():
    test_str = rb"https://chat.deepseek.com/a/chat/s/560d6b0b-ea8a-460e-bddc-54a30f8c257d"
    result = url_tpf.findall(test_str)
    return result


def test_func(name):
    if name == "url_tpf":
        return url_tpf_test()


def find_url(item, mode, pattern):
    urls = []

    if mode == "path":
        # Path创建一个文件管理类来遍历 path(dir_path)类初始化
        item_path = Path(item)
        # rglob '*'=遍历所有文件和文件夹(**包含子文件夹下的所有文件**)
        for item in item_path.rglob("*"):
            # 如果不是文件就略过
            if not item.is_file():
                continue
            else:
                try:
                    data = item.read_bytes()  # 读出二进制数据
                except Exception as err:
                    logging.warning(f"[WARN] <{item.name}> 读取二进制数据失败: {err}")
                    continue

            for match in pattern.findall(data):
                match_str = match.decode('utf-8', errors="ignore")
                url_parts = urlsplit(match_str)
                url_parse = urlunsplit(
                    (url_parts.scheme, url_parts.netloc, url_parts.path, url_parts.query, "")
                )
                urls.append(url_parse)

    elif mode == "bytes":
        for match in pattern.findall(item):
            match_str = match.decode('utf-8', errors="ignore")
            url_parts = urlsplit(match_str)
            url_parse = urlunsplit(
                (url_parts.scheme, url_parts.netloc, url_parts.path, url_parts.query, "")
            )  # 移除请求参数,组成要求固定五个部分
            urls.append(url_parse)

    return list(set(urls))


def sift_url(urls: list, keywords) -> dict:
    matches = {}
    for keyword in keywords:
        if keyword.startswith("/") and len(keyword) > 1:
            key = keyword[1:]
        else:
            key = keyword
        matches[key] = []
        for url in urls:
            if keyword in url:
                if keyword.startswith("/") and len(keyword) > 1:
                    key = keyword[1:]
                else:
                    key = keyword
                matches[key].append(url)

    return matches


def get_round_port(cfg: Configs, method: str, **kwargs):
    if method == "entry_file":
        if kwargs.get("url"):
            url = kwargs.get("url")
            url_parts = urlsplit(url)
            if url_parts.query:
                params = parse_qs(url_parts.query)
                port = params.get("port", [''])[0]
                if port:
                    cfg.round_part = int(port)
                else:
                    raise Exception(f"没有找到url的port参数")


def _get_timestamp(url: str):
    url_parts = urlsplit(url)
    if not url_parts.query:
        return None
    params = parse_qs(url_parts.query)
    timestamp = params.get("time",[''])[0]
    try:
        return int(timestamp)
    except ValueError:
        return None


def _get_version(url: str, debug=False) -> tuple:
    match = version_sign.search(url)

    if not match:
        return (-1, -1, -1) # 圆括号默认 tuple

    version = tuple(map(int, match.groups()))

    if debug:
        print(f"""
version:
完整: {match.group(0)}
大版本: {match.group(1)}
小版本: {match.group(2)}
build: {match.group(3)}""")

    return version


def _get_latest(urls: list[str], cfg: Configs, debug=False) -> int:
    # 筛选区号参数
    if cfg.zone_id:
        filtered_urls = []

        for url in urls:
            # ** for url in urls 本质依旧是索引自增, 所以删除后还是会调到下2个, 也会有范围超过报错风险 **
            params = parse_qs(urlsplit(url).query)
            zone_id = params.get("zone_id", [""])[0]

            # 没有区服参数的是 resource.cfg 等资源，继续保留
            if not zone_id or str(zone_id) == str(cfg.zone_id):
                filtered_urls.append(url)

        # 原地替换，保证外部 url_list 和这里使用的是同一列表
        urls[:] = filtered_urls

    if len(urls) <= 0:
        raise ValueError(f"没有找到指定区服 <{cfg.zone_id}> 相关url")

    # 先判断时间戳
    last_timestamp = -1
    latest_url_index = -1
    for i in range(0, len(urls)):
        timestamp = _get_timestamp(urls[i])
        if not timestamp:
            latest_url_index = -1
            break
        if timestamp > last_timestamp:
            latest_url_index = i
            last_timestamp = timestamp
    if latest_url_index >= 0:
        return latest_url_index

    # 缺失时间戳再判断版本
    versions = []
    for url in urls:
        version = _get_version(url, debug)
        versions.append(version)

    return versions.index(max(versions))


def select_latest(urls: dict, cfg: Configs, debug=False):
    resource_dict = urls

    for key, url_list in resource_dict.items():
        if len(url_list) > 1:
            resource_dict[key] = url_list[_get_latest(url_list, cfg, debug)]
        elif len(url_list) == 1:
            resource_dict[key] = url_list[0]
        else:
            pass

    return resource_dict


def analyze_tbs_cache_front(tbs_cache_path, cfg: Configs):
    """
    # 前置文件总方法 (本地缓存)
    解析请求过的缓存文件，找到关键swf，cfg资源url站点下载，下一步确定socket端口
    :param tbs_cache_path: tbs缓存目录的路径
    :param cfg: 项目全局配置
    :return: requirement: 需要下载的前置资源，一般包括 entry.swf, resource.cfg
    """
    debug = cfg.debug

    urls = find_url(item=tbs_cache_path, mode="path", pattern=url_tpf)
    if debug:
        print(f"all urls in tbs_cache:\n{urls}")
    if len(urls) < 1:
        raise Exception("没有找到缓存url请求记录")

    keywords = cfg.font_resource_keywords
    resource_urls = sift_url(urls, keywords)
    if debug:
        print(f"resource urls:\n{resource_urls}")

    resource_requirement = select_latest(resource_urls, cfg, debug)
    if debug:
        print(f"resource requirement: {resource_requirement}")

    if resource_requirement.get("entry.swf", ""):
        try:
            get_round_port(
                cfg=cfg,
                method="entry_file",
                url=resource_requirement.get("entry.swf"),
            )
            logging.info(f"[INFO] 找到通信端口: {cfg.round_part}")
        except Exception as err:
            logging.warning(f"[WARN] {err}")

    return resource_requirement


def analyze_tbs_cache_after(cfg: Configs):
    """
    # 后置文件总方法
    :param cfg: 项目全局配置
    :return:
    """
    debug = cfg.debug
    resource_dir = cfg.resource_save_path

    # part1 分析resource得到必要组件的指向
    ## 解压缩
    resource_cfg_path = os.path.join(resource_dir, "resource.cfg")
    resource_cfg_path = Path(resource_cfg_path)
    if resource_cfg_path.exists() and resource_cfg_path.is_file():
        origin_data = resource_cfg_path.read_bytes()
        decompressed_data, _ = decompress_manager.decompress_bytes(origin_data)
    else:
        raise FileNotFoundError(f"resource.cfg文件路径不存在或无效: {resource_cfg_path}")

    if not decompressed_data:
        raise Exception(f"resource.cfg文件解压失败或内容为空")
    ## 读取
    if decompressed_data[4] == 0x11:
        # print("amf3格式")
        resource_cfg_data_type = "amf3"
    else:
        raise TypeError(f"resource.cfg 格式未知")

    # resource 找 flash.core.swf 索引
    resource_cfg_dict = type_reader_manager.read_bytes(decompressed_data, resource_cfg_data_type)
    resource_urls = {}
    for keyword in cfg.after_resource_keywords:
        if keyword.startswith("/") and len(keyword) > 1:
            key = keyword[1:]
        else:
            key = keyword
        resource_urls[key] = []

    for item_name, rule in resource_cfg_dict.items():
        for keyword in cfg.after_resource_keywords:
            if keyword.startswith("/") and len(keyword) > 1:
                key = keyword[1:]
            else:
                key = keyword
            try:
                if keyword in rule["url"]:
                    resource_url = urlunsplit([
                        "https",
                        "res.huoying.qq.com",
                        f"/{rule['tag']}/{rule['url']}",
                        "",
                        "",
                    ])
                    resource_urls[key].append(resource_url)
            except TypeError:
                continue

    resource_requirement = select_latest(resource_urls, cfg, debug)
    if debug:
        print(f"resource_requirement: {resource_requirement}")

    yield resource_requirement

    # part2 解密

    naruto_server_swf_path = os.path.join(cfg.resource_save_path,"flash/server/NarutoServer.swf")
    # print(f"aim: {naruto_server_swf_path}")

    decrypt_manager.decrypt_file(naruto_server_swf_path, debug)


if __name__ == "__main__":
    # print("当前工作目录:", Path.cwd())
    # print("实际查找位置:", resource_cfg_path.resolve())
    from net import get_net_client

    cfg = Configs()
    cfg.initialization_configs(r"../config.yaml")
    gen = analyze_tbs_cache_after(cfg)

    try:
        resource_requirement = next(gen)
    except Exception as err:
        print(f"[ERROR] 后处理 part1 意外错误: {err}")

    net_client = get_net_client(cfg)

    try:
        net_client.download_requirement(resource_requirement, cfg.resource_save_path)
    except Exception as err:
        print(f"[ERROR]下载失败: {err}")

    try:
        next(gen)
    except StopIteration as err:
        pass
    except Exception as err:
        print(f"[ERROR] 后处理 part2 意外错误: {err}")