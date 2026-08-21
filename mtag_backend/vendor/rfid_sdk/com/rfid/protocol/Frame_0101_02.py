from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# R2000直流偏置校准参数查询
class Frame_0101_02(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0101"
            self._CW._CW_MID = 0x02
            self._Data_Len = 0

        except Exception as e:
            raise RuntimeError("Frame_0101_02(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Parameter save failed",
                         2: "2|Other error"}

    def GetReturnData(self):
        return bytearray([self._Data[0] & 0xFF])
