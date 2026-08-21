from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 读写器功率校准参数查询
class Frame_0101_04(BaseFrame):
    # 校准的子频段 功率等级
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0101"
            self._CW._CW_MID = 0x04
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                listData.append(data[0])
                listData.append(data[1])
                self._Data = Helper_String.ArraylisttoBytes(listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0101_04(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Parameter save failed",
                         2: "2|Other error"}

    def GetReturnData(self):
        return (self._Data[0] & 0xFF) + "|" + (self._Data[1] & 0xFF) + "|" + (self._Data[2] & 0xFF)
