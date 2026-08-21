from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询读写器自检功能
class Frame_0001_2E(BaseFrame):
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x2E
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_2E(),Error!" + str(e))


    def GetReturnData(self):
        if len(self._Data) == 1:
            return self._Data[0]
        else:
            return (0xff & self._Data[0]) + "|" + (0xff & self._Data[2]) + "." + (0xff & self._Data[3]) \
                   + "." + (0xff & self._Data[4]) + "." + (0xff & self._Data[5])

