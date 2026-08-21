from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

class Frame_0010_FF(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0xFF
            self._Data_Len = 0
            if data:
                super().__init__(data)
        except Exception as e:
            raise RuntimeError("Frame_0010_FF(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|System error"}
    # 查询结果 255|255
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
