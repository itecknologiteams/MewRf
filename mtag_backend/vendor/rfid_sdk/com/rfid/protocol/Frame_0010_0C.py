from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询EPC基带速率
class Frame_0010_0C(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x0C
            self._Data_Len = 0
            if data:
                super().__init__(data)
        except Exception as e:
            raise RuntimeError("Frame_0010_0C(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}
    #  0~255 | 0~255 |  0~255 | 0~255
    def GetReturnData(self):
        rt = str(self._Data[0] & 0xFF) + "|" + str(self._Data[1] & 0xFF) + "|" + str(self._Data[2] & 0xFF) + "|" + str(self._Data[3] & 0xFF)
        return rt