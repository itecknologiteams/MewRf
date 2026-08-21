from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


# 查询功率
class Frame_0010_02(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x02
            self._Data_Len = 0
            if data:
                super().__init__(data)
        except Exception as e:
            raise RuntimeError("Frame_0010_02(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The port parameter is not supported in hardware of reader",
                         2: "2|The power parameter is not supported in hardware of reader",
                         3: "3|Save failure"}

    def GetReturnData(self):
        rt = ""
        for i in range(0,len(self._Data),2):
            rt += str(self._Data[i]) + "," + str(self._Data[i + 1] ) + "&"
        if rt.endswith("&"):
            rt = rt[0: len(rt) -1]
        return rt