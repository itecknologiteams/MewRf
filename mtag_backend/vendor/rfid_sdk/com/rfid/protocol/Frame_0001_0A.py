from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


class Frame_0001_0A(BaseFrame):
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x0A
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_0A(),Error!" + str(e))

    # 1, 0 & 2, 0 & 3, 0 & 4, 0
    def GetReturnData(self):
        rt = ""
        if len(self._Data) > 0:
            copyIndex = 0
            while copyIndex < len(self._Data):
                rt += str(self._Data[copyIndex]) + "," + str(self._Data[copyIndex + 1]) + "&"
                copyIndex += 2
            rt = rt.rstrip('&')
        return rt
