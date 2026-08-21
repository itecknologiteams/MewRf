from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

class Frame_0001_0E(BaseFrame):
    # 查询韦根通信参数
    def __init__(self,*data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x0E
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_0E(),Error!" + str(e))

    # 0 | 触发绑定的指令 | 0 | U16
    def GetReturnData(self):
        rt = ""
        if len(self._Data) > 0:
            rt += (0xff & self._Data[0]) + "|" + (0xff & self._Data[1]) + "|" + (0xff & self._Data[2])
            if len(self._Data) == 5:
                rt += "|" + (0xff & self._Data[3]) + "," + (0xff & self._Data[4])
        return rt

