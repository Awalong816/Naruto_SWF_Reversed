import psutil

# 多同名进程
def get_client_running_info(client_name: str, findall=False, debug=False):
    fits = []

    for processes in psutil.process_iter(["name", "pid"]):
        # print(f"name: {processes.name()} pid: {processes.pid}")
        if client_name.strip().casefold() in processes.name().strip().casefold():
            fits.append({
                "name": processes.name(),
                "pid": processes.pid
            })
            if debug:
                print(f"name: {processes.name()} pid: {processes.pid}")
            if not findall:
                break

    if len(fits) <= 0:
        raise Exception(f"No program named {client_name} found")

    processes = {}

    # 所有最高层进程 父
    for index in range(0,len(fits)):
        pid = fits[index]["pid"]
        pack = _get_child(pid)
        key = fits[index]["name"] + "_" + str(fits[index]["pid"])
        processes[key] = pack

    for process in processes.values():
        for index in range(0,len(process)):
            process[index]["ports"] = _get_port(process[index]["pid"])

    return processes

# 多子进程，多层子进程
def _get_child(pid):
    """
    根据 PID 获取所有子进程，包括多层子进程。
    """
    parent = psutil.Process(pid)
    process = [{
        "name": parent.name(),
        "pid": parent.pid,
    }]

    children = parent.children(recursive=True)
    for child in children:
        process.append({
            "name": child.name(),
            "pid": child.pid,
        })

    return process

# 多端口
def _get_port(pid):
    ports = []
    process = psutil.Process(pid)

    for connection in process.net_connections(kind="tcp"):
        if connection.status == psutil.CONN_ESTABLISHED and connection.laddr:
            ports.append(connection.laddr.port)

    ports = sorted(ports)
    return ports

def _test(client_name: str):
    return get_client_running_info(client_name, findall=True, debug=True)

if __name__ == '__main__':
    input_name = input("测试进程名字: ")
    input_name = (input_name.strip() or "qqgame")
    print(f"测试结果: {_test(input_name)}")