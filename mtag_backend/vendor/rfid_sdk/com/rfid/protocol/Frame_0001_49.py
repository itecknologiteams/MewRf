from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 心跳设置查询
class Frame_0001_49(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x49
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_49(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Param error",
                         2: "2|Save failed"}

    def GetReturnData(self):
        rt = ""
        if len(self._Data) == 4:
            rt += (Helper_String.GetU16ByBytes(self._Data, 0)+"|")
            rt += Helper_String.GetU16ByBytes(self._Data, 2)
        return rt
