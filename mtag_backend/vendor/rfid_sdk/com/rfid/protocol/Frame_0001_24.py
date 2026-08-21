from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 获取白名单动作参数
class Frame_0001_24(BaseFrame):
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x24
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_24(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        rt = ""
        index = 0
        for i in range(0,len(self._Data)):
            if i == 2:
                continue
            if i == 1:
                rt += self._Data[i] + "" + self._Data[i + 1] + "|"
            else:
                rt += self._Data[i] + "|"

        rt = rt[0:len(rt)-1]
        return rt
