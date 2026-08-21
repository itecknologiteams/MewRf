from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 6B标签锁定查询
class Frame_0010_43(BaseFrame):
    # 天线端口|待锁定标签TID|锁定地址
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x43
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                arrParam = data[0].rstrip("|").split("|")

                self.listData.append(int(arrParam[0]) & 0xff)
                dataLen += 1
                self.listData.append(Helper_String.hexStringToBytes(arrParam[1]))
                dataLen += len(arrParam[1]) / 2
                self.listData.append(arrParam[2])
                dataLen += 1
                if len(arrParam) >= 4:
                    varParams = arrParam[3].rstrip("&").split("&", -1)
                    for item in varParams:
                        tempItem = item.rstrip(",").split(",", -1)
                        self.listData.append(int(tempItem[0]) & 0xff)
                        self.listData.append(Helper_String.hexStringToBytes(tempItem[1]))
                self._Data = [0 for x in range(0,dataLen)]
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_43(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Other error"}
    DIC_LOCK = {0: "0|Unlock",
                1: "0|Lock"}

    def GetReturnData(self):
        index = self._Data[0] & 0xff
        if index != 0:
            return self.DIC_RESPONSE_CODE.get(index)
        else:
            return self.DIC_LOCK.get(self._Data[2] & 0xff)  # 可选参数，所是下标是2;