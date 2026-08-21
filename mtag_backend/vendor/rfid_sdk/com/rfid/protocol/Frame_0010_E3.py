from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询可选上传参数
class Frame_0010_E3(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0xE3
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0010_E3(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The parameter is not supported in hardware of reader"}
    # 1,0 & 2,0 & 3,0 & 4,0
    def GetReturnData(self):
        rt = ""
        if len(self._Data) > 0:
            copyIndex = 0
            while copyIndex < len(self._Data) :
                rt += self._Data[copyIndex]
                copyIndex += 1
                rt += "," + self._Data[copyIndex] + "&"
                copyIndex += 1
            rt = rt.rstrip('&')
        return rt
