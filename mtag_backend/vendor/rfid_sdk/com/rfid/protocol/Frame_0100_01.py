from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 升级基带软件指令
class Frame_0100_01(BaseFrame):

    def __init__(self,dataIndex, *data):
        try:
            super().__init__()
            if len(data) > 1000:
                raise  RuntimeError("Overflow!")
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0100"
            self._CW._CW_MID = 0x01
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                self.listData.append(Helper_String.BytesToArraylist(Helper_Protocol.ReverseLongToU32Bytes(dataIndex)))
                self.listData.append(Helper_String.BytesToArraylist(Helper_Protocol.ReverseIntToU16Bytes(len(data))))
                self.listData.append(Helper_String.BytesToArraylist(data))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0100_01(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|System error"}

    def GetReturnData(self):
        rt = ""
        try:
            dataIndex = Helper_String.GetU32ByBytes(self._Data, 0)
            rt = dataIndex + "|" + self._Data[4]
        except Exception as e:
            pass
        return rt
