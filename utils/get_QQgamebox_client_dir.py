import os

def get_qqgamebox_client_path():
    """
    拿到游戏本体(当前只能从QQ游戏大厅启动)/QQ游戏大厅客户端的位置
    :return: 目录的绝对路径
    """
    appdata_env_path = os.environ.get("APPDATA","") # get的正常用法
    # return str(appdata_env_path)

    # 存在于标准位置
    if appdata_env_path:
        client_dir_path = os.path.join(appdata_env_path, "Tencent", "QQMicroGameBox")
        if os.path.isdir(client_dir_path):
            return os.path.abspath(str(client_dir_path))
    # 搜索其他位置 不作处理

    raise NotADirectoryError("找不到客户端本地位置")

if __name__ == "__main__":
    print(f"result: {get_qqgamebox_client_path()}")

