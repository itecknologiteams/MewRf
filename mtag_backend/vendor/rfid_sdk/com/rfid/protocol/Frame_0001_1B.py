from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

class Frame_0001_1B(BaseFrame):
    # 查询断点续传缓存数据
    def __init__(self,*data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x1B
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_1B(),Error!" + str(e))

    # 查询返回0为有缓存数据，1为无缓存数据，2数据返回结束
    def GetReturnData(self):
        return self._Data[0]

