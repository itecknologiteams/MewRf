from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询UTC
class Frame_0001_11(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x11
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_11(),Error!" + str(e))

    def GetReturnData(self):
        return str(self.GetS32ByBytes(self,self._Data, 0)) + "." + str(int(self.GetS32ByBytes(self,self._Data, 4) / 1000))

    def GetS32ByBytes(self, data, startIndex):
        rt = 0
        try:
            tempByte = bytearray(4)
            Helper_Protocol.arrayCopy(data, startIndex, tempByte, 0, 4)
            rt = self.ByteArrayToInt(self,tempByte)
        except Exception as e:
            raise RuntimeError("Frame_0001_11(),Error!" + str(e))
        return rt

    def ByteArrayToInt(self,b):
        return b[3] & 0xFF | (b[2] & 0xFF) << 8 | (b[1] & 0xFF) << 16 | (b[0] & 0xFF) << 24