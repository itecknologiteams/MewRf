from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# WiFi热点搜索
class Frame_0001_31(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x31
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_31(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Not supports"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
