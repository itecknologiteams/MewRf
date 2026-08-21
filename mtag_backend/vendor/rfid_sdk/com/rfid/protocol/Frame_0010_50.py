from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 读国标标签
class Frame_0010_50(BaseFrame):
    # 天线端口 | 连续 / 单次读取 | 1, 读取参数 & 2, TID读取参数 & 3, 用户数据区读取参数 & 5, 标签访问密码
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x50
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                arrParam = data[0].rstrip("|").split("|", -1)
                self.listData.append(int(arrParam[0]) & 0xff)
                self.listData.append(int(arrParam[1]) & 0xff)
                if len(arrParam) == 3:
                    varParams = arrParam[2].rstrip("&").split("&", -1)
                    for item in varParams:
                        tempItem = item.rstrip(",").split(",", -1)
                        if tempItem[0] == "1":
                            self.listData.append(tempItem[0])
                            tempItem[1] = self.ByteToString(Helper_String.GetReverseU16(int(len(tempItem[1]) / 2))) + tempItem[1]
                            self.listData.append(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(tempItem[1])))
                        else:
                            self.listData.append(int(tempItem[0]) & 0xff)
                            self.listData.append(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(tempItem[1])))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_50(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The antenna port parameter error",
                         2: "2|Read content parameter error",
                         3: "3|TID read parameter error",
                         4: "4|Userdata read parameter error",
                         5: "5|Other parameter error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
    # 字节数据转16进制
    @staticmethod
    def ByteToString(vArrData):
        ByteString = ""
        for i in range(0,len(vArrData)):
            ByteString += "{:x}".format(vArrData[i])
        return ByteString
