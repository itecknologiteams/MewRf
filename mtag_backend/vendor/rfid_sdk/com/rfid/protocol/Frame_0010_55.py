from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 断点续传数据应答
class Frame_0010_55(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x55
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                Param = data[0]
                listData.append(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(Param)))

                self._Data = Helper_String.ArraylisttoBytes(listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_55(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Other Error"}

    def GetReturnData(self):
        return super().GetReturnData()