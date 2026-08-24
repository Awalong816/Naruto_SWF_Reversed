def read_bytes(path: str):
    with open(path, "rb") as file:
        data = file.read()
        content = str(data)
    if content:
        return content

if __name__ == "__main__":
    file_path = "C:/Users/DELL/AppData/Roaming/Tencent/QQMicroGameBox/tbs_cache/0/Cache/data_0"
    result = read_bytes(file_path)
    print(f"result content:\n{result}")