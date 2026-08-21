from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 读写器透传
class Frame_0001_F0(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0xF0
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                send = Helper_String.hexStringToBytes(data[0])
                self.listData.append(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(len(send))))
                self.listData.append((Helper_String.BytesToArraylist(send)))

                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0001_F0(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return Helper_String.Bytes2String(self._Data, 2, len(self._Data)- 2)


