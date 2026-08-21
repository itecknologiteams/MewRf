from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置串口1 参数
class Frame_1010_04(BaseFrame):
    # "115200|8|0|0|0|1|1|1"
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "1010"
            self._CW._CW_MID = 0x04
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                array_param = data[0].rstrip("|").split("|")
                if len(array_param) > 1:
                    self.listData.append(Helper_Protocol.ReverseLongToU32Bytes(int(array_param[0])))
                    dataLen += 4
                    for i in range(1,len(array_param)):
                        self.listData.append(array_param[i])
                        dataLen += 1
                self._Data = [0 for x in range(0,dataLen)]
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_1010_04(),Error!" + str(e))

    # DIC_RESPONSE_CODE = {0: "0|OK",
    #                      1: "1|Failed"}
    #
    # def GetReturnData(self):
    #     return self.DIC_RESPONSE_CODE.get(self._Data[0])