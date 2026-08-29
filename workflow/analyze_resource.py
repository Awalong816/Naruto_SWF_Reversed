import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 现在可以直接导入
from config import Configs
from utils import get_decompress_manager, get_type_reader_manager

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
                    (url_parts.scheme, url_parts.netloc, url_parts.path, "", ""))  # 移除请求参数,组成要求固定五个部分
                urls.append(url_parse)

    elif mode == "bytes":
        for match in pattern.findall(item):
            match_str = match.decode('utf-8', errors="ignore")
            url_parts = urlsplit(match_str)
            url_parse = urlunsplit(
                (url_parts.scheme, url_parts.netloc, url_parts.path, "", ""))  # 移除请求参数,组成要求固定五个部分
            urls.append(url_parse)

    return list(set(urls))


def sift_url(urls: list, keywords):
    matches = []
    for keyword in keywords:
        for url in urls:
            if keyword in url:
                matches.append(url)

    return matches


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


def _get_latest(urls: list[str], debug=False) -> int:
    versions = []
    for url in urls:
        version = _get_version(url, debug)
        versions.append(version)

    return versions.index(max(versions))


def select_version(urls: list, keywords, debug=False):
    resource_dict = {}

    for keyword in keywords:
        if keyword.startswith("/") and len(keyword) > 1:
            keyword = keyword[1:]

        resource_dict[keyword] = []

        for url in urls:
            if keyword in url:
                resource_dict[keyword].append(url)

    for key, url_list in resource_dict.items():
        if len(url_list) > 1:
            resource_dict[key] = url_list[_get_latest(url_list, debug)]
        else:
            resource_dict[key] = url_list[0]

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

    resource_requirement = select_version(resource_urls, keywords, debug)
    if debug:
        print(f"resource requirement: {resource_requirement}")

    return resource_requirement


def analyze_tbs_cache_after(cfg: Configs):
    """
    # 后置文件总方法
    :param cfg: 项目全局配置
    :return:
    """
    debug = cfg.debug
    resource_dir = cfg.resource_save_path

    # 分析resource得到core的指向
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
    resource_url_list = []

    for item_name, rule in resource_cfg_dict.items():
        for keyword in cfg.after_resource_keywords:
            try:
                if keyword in rule["url"]:
                    resource_url = urlunsplit([
                        "https",
                        "res.huoying.qq.com",
                        f"/{rule['tag']}/{rule['url']}",
                        "",
                        "",
                    ])
                    resource_url_list.append(resource_url)
            except TypeError:
                continue

    if len(resource_url_list) < 1:
        raise ValueError(f"resource文件没有找到 <{cfg.after_resource_keywords}> 记录")

    resource_requirement = select_version(resource_url_list, cfg.after_resource_keywords, debug)
    if debug:
        print(f"resource_requirement: {resource_requirement}")

    return resource_requirement


if __name__ == "__main__":
    # print("当前工作目录:", Path.cwd())
    # print("实际查找位置:", resource_cfg_path.resolve())
    from net import get_net_client

    cfg = Configs()
    cfg.initialization_configs(r"../config.yaml")
    resource_requirement = analyze_tbs_cache_after(cfg)

    net_client = get_net_client(cfg)

    try:
        net_client.download_requirement(resource_requirement, cfg.resource_save_path)
    except Exception as err:
        print(f"[ERROR]下载失败: {err}")