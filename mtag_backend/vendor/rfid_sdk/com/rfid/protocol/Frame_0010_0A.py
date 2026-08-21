from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


class Frame_0010_0A(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x0A
            self._Data_Len = 0
            if data:
                super().__init__(data)
        except Exception as e:
            raise RuntimeError("Frame_0010_0A(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    # 0~65535 | 0~255
    def GetReturnData(self):
        rt = ""
        shortArr = bytearray(2)
        Helper_Protocol.arrayCopy(self._Data, 0, shortArr, 0, 2)

        rt += str(Helper_String.ByteArrayToInt1(shortArr)) + "|"
        rt += str(self._Data[2] & 0xFF) + "|"
        if len(self._Data) == 4:
            #可选参数dBm阈值
            rt += self._Data[3] & 0xFF
        return rt


