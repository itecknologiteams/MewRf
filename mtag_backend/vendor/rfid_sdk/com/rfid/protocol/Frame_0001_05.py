from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询读写器IP
class Frame_0001_05(BaseFrame):
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x05
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_05(),Error!" + str(e))

    def GetReturnData(self):
        rt = ""
        rt += str(int(self._Data[0] & 0xff)) + "." + str(int(self._Data[1] & 0xff)) + "." + str(int(self._Data[2] & 0xff)) + "." + str(int(self._Data[3] & 0xff)) + "|"
        rt += str(int(self._Data[4] & 0xff)) + "." + str(int(self._Data[5] & 0xff)) + "." + str(int(self._Data[6] & 0xff)) + "." + str(int(self._Data[7] & 0xff)) + "|"
        rt += str(int(self._Data[8] & 0xff)) + "." + str(int(self._Data[9] & 0xff)) + "." + str(int(self._Data[10] & 0xff)) + "." + str(int(self._Data[11] & 0xff)) + "|"
        i = 12
        while i < len(self._Data):
            if self._Data[i] == 0x01:
                rt += str(int(self._Data[i] & 0xff)) + "," + str(int(self._Data[i + 1] & 0xff)) + "." + str(int(self._Data[i + 2] & 0xff)) + "." + str(int(self._Data[i + 3] & 0xff)) + "." \
                      + str(int(self._Data[i + 4] & 0xff)) + "&"
                i += 5
            elif self._Data[i] == 0x60:
                rt += str(int(self._Data[i] & 0xff)) + "," + str(int(self._Data[i + 1] & 0xff)) + "&"
                i += 2
            elif self._Data[i] == 0x61:
                rt += str(int(self._Data[i] & 0xff)) + "," + str(Helper_String.ByteToStringHigh(self._Data, i + 1,2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 3, 2)) + ":" \
                      + str(Helper_String.ByteToStringHigh(self._Data, i + 5, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 7, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 9, 2)) + ":" \
                      + str(Helper_String.ByteToStringHigh(self._Data, i + 11, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 13, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 15,2)) + "&"
                i += 17
            elif self._Data[i] == 0x62:
                rt += str(int(self._Data[i] & 0xff)) + "," + str(int(self._Data[i + 1] & 0xff)) + "&"
                i += 2
            elif self._Data[i] == 0x63:
                rt += str(int(self._Data[i] & 0xff)) + "," + str(Helper_String.ByteToStringHigh(self._Data, i + 1,2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 3, 2))\
                      + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 5, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 7, 2))\
                      + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 9, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 11, 2))\
                      + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 13, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 15,2)) + "&"
                i += 17
            elif self._Data[i] == 0x64:
                rt += str(int(self._Data[i] & 0xff)) + "," + str(Helper_String.ByteToStringHigh(self._Data, i + 1, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 3, 2))\
                      + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 5, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 7, 2))\
                      + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 9, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 11, 2))\
                      + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 13, 2)) + ":" + str(Helper_String.ByteToStringHigh(self._Data, i + 15, 2)) + "&"
                i += 17
        rt = rt.rstrip('&')
        rt = rt.rstrip('|')
        return rt

