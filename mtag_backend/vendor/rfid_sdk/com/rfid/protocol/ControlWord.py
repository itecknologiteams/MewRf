import math

import six


class ControlWord:
    def __init__(self, *data):
        self._CW_MID = 0xFF
        self._CW_8_11 = '0000'
        self._CW_12 = '0'
        self._CW_13 = '0'
        self._CW_14 = '0'
        self._CW_15 = '0'
        if data:
            self._CW_MID = data[0]
            self._CW_8_11 = data[1]
            self._CW_12 = data[2]
            self._CW_13 = data[3]

    # 解析协议控制字，高位在前低位在后
    def SetData(self,data):
        try:
            self._CW_MID = data[1]
            s_CW_b = self.byte2bits(data[0])
            s_CW_b = s_CW_b.ljust(8,'0')
            self._CW_8_11 = s_CW_b[4: 8]
            self._CW_12 = s_CW_b[3: 4]
            self._CW_13 = s_CW_b[2: 3]
            self._CW_14 = s_CW_b[1: 2]
            self._CW_15 = s_CW_b[0: 1]
            return self
        except Exception as e:
            print("失败，错误信息%s" % e)

    # 获取协议字控制字，高位在前低位在后
    def GetBytes(self):
        rt = bytearray(2)
        try:
            s_CW_B = self._CW_15 + self._CW_14 + self._CW_13 + self._CW_12 + self._CW_8_11
            b_CW_B = self.bit2bytes(s_CW_B)
            rt[0] = int(b_CW_B)
            rt[1] = self._CW_MID
        except Exception as e:
            print("失败，错误信息%s" % e)
        return rt

    @staticmethod
    def bit2bytes(bString):
        result = 0
        j = 0
        for i in ''.join(reversed(bString)):
            result += int(i) * math.pow(2, j)
            j += 1
        return result

    def byte2bits(self,b):
        z = b
        z |= 256
        str = bin(z)
        lena = len(str)
        return str[lena - 8: lena]