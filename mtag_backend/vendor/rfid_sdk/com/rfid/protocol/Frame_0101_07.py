from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# pr9200 PA反馈校准参数查询。
class Frame_0101_07(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0101"
            self._CW._CW_MID = 0x07
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                self._Data = Helper_String.ArraylisttoBytes(listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0101_07(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Parameter save failed",
                         2: "2|Other error"}

    def GetReturnData(self):
        RES_1 = (self._Data[0] & 0xF0) >> 4
        RES_2 = self._Data[0] & 0x0F

        return RES_1 + "|" + RES_2
