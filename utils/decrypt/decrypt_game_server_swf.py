class NarutoServerDecryptManager:
    def __init__(self):
        pass

    def decrypt(self, data: bytes, device="latest", **kwargs):
        func_head = "_decrypt_naruto_server_swf_"
        if device == "latest":
            functions = []
            for f in dir(self):
                if f.startswith(func_head):
                    functions.append(f.split("_")[-1])

            if not functions:
                return data

            if len(functions) == 1:
                version = functions[0]
            elif len(functions) > 1:
                version = max(functions)

            func_name = func_head + version

            return getattr(self, func_name)(data)

        elif device == "id":
            func_id = kwargs.get("version")
            if not str(func_id).strip().startswith(func_head):
                func_name = func_head + func_id
            else:
                func_name = func_id
            try:
                return getattr(self, func_name)(data)
            except Exception as err:
                return data

        else:
            return data

    def _decrypt_naruto_server_swf_260830(self, data: bytes):
        """
        自定义混淆: 前四位标志位 b 'ZWS\x00' + 内容长度
        :param data: 混淆的原字节流
        :return: LZMA字节流
        """
        # 筛选
        if len(data) < 8:
            return
        else:
            # 1. 筛选混淆标志
            if not data.startswith(b"ZWS\x00"):
                return data
            # 2. 筛选长度位掩码
            if data[4:8] != b"\xff\xff\xff\xff":
                return data

        # 解除交叉混淆
        p = 8  # <- 开始位置指针
        step = 11
        turn_case = data[p:p + step]  # 11个
        p += step  # 移动开始指针

        double_index = turn_case[0::2]  # [0,2,...]
        single_index = turn_case[1::2]  # [1,3,...]

        result = bytearray()  # bytes与bytearray区别: 不可修改|可修改

        # 组合新字节,方式: 取两个一组字节的低4位(8位的后4位，按正常读数方法--百十个)按顺序组成新字节(2号在高位)
        for bp in range(0, len(double_index), 2):
            low = double_index[bp] & 0x0F  # 00001111
            high = double_index[bp + 1] & 0x0F  # 00001111
            high = high << 4

            new_p1 = high | low

            result.append(new_p1)

        result.extend(single_index)

        # 前128字节中，奇数位置按位取反
        encrypted_length = min(128, len(data) - p)

        for index in range(p, p + encrypted_length, 2):
            # 判断索引奇数位置 *注意 and与&不等效, 参考c,go的&&与&的区别
            if index % 2 == 1:
                new_p2 = (~data[index]) & 0xFF  # &0xFF: 取反位置会拉长(由语言下的储存类型决定, py的int/float...界限不明, 所以是前导无限位)
                # **无限高位1的问题，最高位为1视为负数，会取补码(再取反+1)导致成为非数学意义取反**
                # 例子: 90 = 0101 1010, 数学取反=1010 0101=165, 正负值取反=(-)0101 1011=-91
                # 还是八位存储不会拉长数据的长度
                result.append(new_p2)

        p += encrypted_length
        result.extend(data[p:])

        return bytes(result)


def get_naruto_server_decrypt_manager():
    return NarutoServerDecryptManager