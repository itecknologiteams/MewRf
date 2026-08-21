from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询读写器MAC
class Frame_0001_06(BaseFrame):
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x06
            self._Data_Len = 0

        except Exception as e:
            raise RuntimeError("Frame_0001_06(),Error!" + str(e))


    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        rt = ""
        for item in self._Data:
            rt += "{:x}".format(item) + "-"
        rt = rt.rstrip('-')
        return rt

