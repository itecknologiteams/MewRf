from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 获取UDP参数
class Frame_0001_5D(BaseFrame):
    # 参数 0A0B|C0A80164
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x5C
            self._Data_Len = 0

        except Exception as e:
            raise RuntimeError("Frame_0001_5C(),Error!" + str(e))


    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        # 90 95 C0 A8 01 64
        rt = ""
        rt = int(Helper_String.PrintHexString(self._Data[0]).toUpperCase() + Helper_String.PrintHexString(self._Data[1]).toUpperCase(),16) + "|"
        for i in range(2,len(self._Data)):
            rt += (self._Data[i] & 0xFF) + "."
        rt = rt.rstrip('.')
        return rt

