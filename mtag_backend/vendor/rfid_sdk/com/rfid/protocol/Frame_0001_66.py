from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询读写器StateLED
class Frame_0001_66(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x66
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_66(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    # 0|9090|192.168.1.1|9090
    def GetReturnData(self):
        rt = ""
        rt += str(self._Data[0] & 0xff) + "|"
        pos = 1
        while pos < len(self._Data):
            pid = self._Data[pos] & 0xff
            if pid == 0x01:
                time = Helper_String.GetU16ByBytes(self._Data, pos + 1)
                rt += "1," + str(time) + "&"
                pos += 3
            else:
                break
        if rt.endswith("&"):
            rt = rt[0: len(rt) - 1]
        if rt.endswith("|"):
            rt = rt[0: len(rt) - 1]
        return rt


