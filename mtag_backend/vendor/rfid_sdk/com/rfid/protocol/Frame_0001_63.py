from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询读写器NTP功能
class Frame_0001_63(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x63
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_63(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        rt = str(self._Data[0] & 0xff) + "|"
        ip = None
        host = None
        pos = 1
        while pos < len(self._Data):
            pid = self._Data[pos] & 0xff
            if pid == 1:
                ip = str(self._Data[pos + 1] & 0xff) + "." + str(self._Data[pos + 2] & 0xff) + "." + str(self._Data[pos + 3] & 0xff) + "." + str(self._Data[pos + 4] & 0xff)
                pos += 5
            elif pid == 161:
                dataLen = Helper_String.GetU16ByBytes(self._Data, pos + 1)
                realData = bytearray(len(dataLen))
                Helper_Protocol.arrayCopy(self._Data, pos + 3, realData, 0, len(realData))
                host = str(realData, encoding='utf-8')
                pos += dataLen + 3
        if host != None and host != "":
            rt += host
        elif ip != None and ip != "":
            rt += ip
        rt = rt.rstrip( '|')
        return rt


