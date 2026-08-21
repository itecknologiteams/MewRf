from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 读6B标签
class Frame_0010_40(BaseFrame):
    # 天线端口|连续/单次读取|读取内容(0-1-2)|1,用户数据读取参数 & 2,待匹配的TID
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x40
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                arrParam = data[0].rstrip("|").split("|")
                self.listData.append(int(arrParam[0]))
                dataLen += 1
                self.listData.append(int(arrParam[1]))
                dataLen += 1
                self.listData.append(int(arrParam[2]))
                dataLen += 1
                if len(arrParam) == 4:
                    varParams = arrParam[3].rstrip("&").split("&")
                    for item in varParams:
                        tempItem = item.rstrip(",").split(",")
                        self.listData.append(tempItem[0])
                        dataLen += 1
                        tempStr = ""
                        if len(tempItem[1]) < 4:
                            for i in range(0,4 - len(tempItem[1])):
                                tempStr += "0"
                        tempStr = tempStr + tempItem[1]
                        bParam = Helper_String.hexStringToBytes(tempStr)
                        self.listData.append(bParam)
                        dataLen += len(bParam)
                self._Data = [0 for x in range(0,dataLen)]
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_40(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The antenna port parameter error",
                         2: "2|Read content parameter error",
                         3: "3|Userdata read parameter error",
                         4: "4|Other error"}

    def GetReturnData(self):
        return  super().GetReturnData()