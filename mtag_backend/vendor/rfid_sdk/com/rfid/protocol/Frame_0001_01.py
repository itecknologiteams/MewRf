import six

from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

class Frame_0001_01(BaseFrame):
    # 获得基带软件版本
    def __init__(self):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x01
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_01(),Error!" + str(e))

    def GetReturnData(self):
        rt = "V"
        if (self._Data[0] == 0 and self._Data[1] == 0): # 两位版本
            rt += str(self._Data[2]) + "." + str(self._Data[3])
        elif self._Data[0] == 0: # 三位版本
            rt += str(self._Data[1]) + "." + str(self._Data[2]) + "." + str(self._Data[3])
        else: # 四位版本
            rt += str(self._Data[0]) + "." + str(self._Data[1]) + "." + str(self._Data[2]) + "." + str(self._Data[3])
        return rt


