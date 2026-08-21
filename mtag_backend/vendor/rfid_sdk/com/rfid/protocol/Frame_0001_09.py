from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置GPO状态
class Frame_0001_09(BaseFrame):
    
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x09
            self._Data_Len = 0
            self.listData = bytearray()
            dataLen = 0
            if data:
                arrParam = data[0].rstrip("&").split("&")
                for item in arrParam:
                    arrItem = item.rstrip(",").split(",")
                    if len(arrItem) == 2:
                        self.listData.append(int(arrItem[0])& 0xff)
                        self.listData.append(int(arrItem[1])& 0xff)
                        dataLen += 2
                self._Data = [0 for x in range(0,dataLen)]
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0001_09(),Error!" + str(e))


    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The port parameter is not supported in hardware of reader"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])

