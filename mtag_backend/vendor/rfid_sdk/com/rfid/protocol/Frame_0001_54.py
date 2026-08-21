from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 扫描头数据上报
class Frame_0001_54(BaseFrame):
    # 扫描头数据上报
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x54
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_54(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        rt = ""
        if len(self._Data) > 0:
            for i in range(0,len(self._Data)):
                if i == 0:
                    rt += self._Data[i] + "|"
                elif i > 3:
                    rt += self._Data[i]
        return rt
