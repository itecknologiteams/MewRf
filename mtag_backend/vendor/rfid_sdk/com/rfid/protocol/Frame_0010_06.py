from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


# 查询读写器工作频率
class Frame_0010_06(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x06
            self._Data_Len = 0
            if data:
                super().__init__(data)
        except Exception as e:
            raise RuntimeError("Frame_0010_06(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        rt = str(self._Data[0]) + "|"
        lena = Helper_String.GetU16ByBytes(self._Data, 1)
        for i in range(3,len(self._Data)):
            rt += str(self._Data[i]) + ","
        rt = rt.rstrip( ',')
        return rt