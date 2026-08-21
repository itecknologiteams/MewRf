from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询EPC基带参数
class Frame_0010_0E(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x0E
            self._Data_Len = 0
            if data:
                super().__init__(data)
        except Exception as e:
            raise RuntimeError("Frame_0010_0E(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}
    #  0~255 | 0~65535
    def GetReturnData(self):
        rt = ""
        ulen = self.GetU16ByBytes(self,self._Data, 1)
        rt += str(self._Data[0]) + "|" + str(ulen)
        return rt

    def GetU16ByBytes(self,data,startIndex):
        rt = 0
        try:
            tempByte = bytearray(2)
            Helper_Protocol.arrayCopy(data, startIndex, tempByte, 0, 2)
            tempByte = self.byteConvert(tempByte)
            rt = self.ByteArrayToInt(tempByte)
        except Exception as e:
            raise RuntimeError("Frame_0010_0E(),Error!" + str(e))
        return rt

    @staticmethod
    def ArrayReverse(b):
        temp = [0 for x in range(0,len(b))]
        for i in range(0,len(b)):
            temp[i] = b[len(b) - 1 - i]
        return temp

    @staticmethod
    def ByteArrayToInt(b):
        return (b[1] & 0xFF) | (b[0] & 0xFF) << 8

    @staticmethod
    def byteConvert(b):
        a = b
        for i in range(0,len(b)):
            if b[i] < 0:
                a[i] = bytearray([b[i] & 0xFF])
            else:
                a[i] = b[i]
        return a
