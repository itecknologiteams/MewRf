from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询读写器MAC
class Frame_0001_5E(BaseFrame):
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x5E
            self._Data_Len = 0

        except Exception as e:
            raise RuntimeError("Frame_0001_5E(),Error!" + str(e))

    def GetReturnData(self):
        realData = bytearray(len(self._Data) - 2)
        Helper_Protocol.arrayCopy(self._Data, 2, realData, 0, len(realData))
        try:
            rt = str(realData, encoding='utf-8')
        except Exception as e:
            raise RuntimeError("Frame_0001_5E(),Error!" + str(e))
        return rt

