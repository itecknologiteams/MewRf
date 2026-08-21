from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

class Frame_0001_1D(BaseFrame):

    def __init__(self,*data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x1D
            self._Data_Len = 0
            if data:
                self._Data = data
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_1D(),Error!" + str(e))


