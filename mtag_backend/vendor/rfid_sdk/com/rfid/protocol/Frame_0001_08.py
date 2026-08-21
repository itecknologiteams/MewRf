from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询读写器MAC
class Frame_0001_08(BaseFrame):
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x08
            self._Data_Len = 0

        except Exception as e:
            raise RuntimeError("Frame_0001_08(),Error!" + str(e))


    # // 0|9090|192.168.1.1|9090
    def GetReturnData(self):
        rt = ""
        rt += str((self._Data[0] & 0xff)) + "|"
        rt += str(Helper_String.GetU16ByBytes(self._Data, 1)) + "|"
        serverip = str(self._Data[3] & 0xff) + "." + str(self._Data[4] & 0xff) + "." + str(self._Data[5] & 0xff) + "." + str(self._Data[6] & 0xff)
        serverport = str(Helper_String.GetU16ByBytes(self._Data, 7))
        serverhost = None
        for pos in range(9,len(self._Data)):
            pid = self._Data[pos] & 0xff
            if 0xA2 == pid:
                lena = Helper_String.GetU16ByBytes(self._Data, pos + 1)
                realData = bytearray(lena)
                Helper_Protocol.arrayCopy(self._Data, pos + 3, realData, 0, len(realData))
                serverhost = str(realData, encoding='utf-8')
                pos += lena + 3
            else:
                break

        if (Helper_String.IsNullOrEmpty(serverhost)):
            rt += serverip
        else:
            rt += serverhost
        rt += "|" + serverport
        return rt

