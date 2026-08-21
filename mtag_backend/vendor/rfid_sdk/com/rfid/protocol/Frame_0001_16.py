from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询读写器RS485设备地址
class Frame_0001_16(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x16
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_16(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Other error"}

    def GetReturnData(self):
        return str((self._Data[0] & 0xFF)) + "|" + str(self._Data[1])
