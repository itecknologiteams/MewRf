from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


# 查询读写器天线
class Frame_0010_08(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x08
            self._Data_Len = 0
            if data:
                super().__init__(data)
        except Exception as e:
            raise RuntimeError("Frame_0010_08(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}
    # 255 | 1, 1 - 2 - 3 - 5 - 7 & 2, 4 - 5 - 6
    def GetReturnData(self):
        rt = ""
        if len(self._Data) >= 1: # 非集线器版本
            rt += str(self._Data[0])
            rt = str(int(rt) & 0xFF) # 转回正常值
        if len(self._Data) > 1: # 集线器版本
            rt += "|"
            i = 1
            while i < len(self._Data):
                if str(self._Data[i]) != "25": # 判断是集线器
                    rt += str(self._Data[i]) + "," # 天线号
                    i += 1
                    len_No = self.ReverseBytesToU16(self._Data, i)
                    i += 2
                    n = 0
                    for j in range(0,len_No):
                        rt += str(self._Data[i + j]) + "-" # 扩展天线号
                        n += 1
                    i += n - 1
                    rt = rt.rstrip('-')
                    rt += "&"
                else: # 判断是通道扩展
                    rt += "25,"
                    rt += Helper_String.PrintHexStringByte(self._Data[i + 1]) + Helper_String.PrintHexStringByte(self._Data[i + 2])
                    i += 2
                i += 1
            rt = rt.rstrip('&')
        return rt

    @staticmethod
    def ReverseBytesToU16(data, startIndex):
        rt = 0
        try:
            tempByte = bytearray(2)
            Helper_Protocol.arrayCopy(data, startIndex, tempByte, 0, 2)
            rt = int(Frame_0010_08.ByteArrayToInt1(tempByte))
        except Exception as e:
            raise RuntimeError("Frame_0010_08(),Error!" + str(e))
        return rt

    @staticmethod
    def ByteArrayToInt1(b):
        return b[1] & 0xFF | (b[0] & 0xFF) << 8