from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


class Frame_0001_1F(BaseFrame):
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x1F
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                self.listData.append(int(data[0][0:2]))
                self.listData.append(int(data[0][2:4]))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_1F(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    # 查询返回0为有缓存数据，1为无缓存数据，2数据返回结束
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])

