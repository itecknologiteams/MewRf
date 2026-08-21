from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

class Frame_0010_E1(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0xE1
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0010_E1(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}
    # 查询结果 255|255
    def GetReturnData(self):
        rt = ""
        for i in range(0,len(self._Data),5):
            rt += str(self._Data[i]) + "," + Helper_String.Bytes2String2(self._Data, i + 1, 4) + "&"
        if rt.endswith("&"):
            rt = rt[0: len(rt) - 1]
        return rt
