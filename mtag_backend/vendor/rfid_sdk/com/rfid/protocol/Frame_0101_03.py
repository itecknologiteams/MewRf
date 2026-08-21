from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 读写器功率校准
class Frame_0101_03(BaseFrame):
    # 待校准的子频段 待校准功率等级 功率校准参数 操作类型
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0101"
            self._CW._CW_MID = 0x03
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                self.listData.append(data[0])
                self.listData.append(data[1])
                self.listData.append(data[2])
                self.listData.append(data[3])
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0101_03(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Parameter save failed",
                         2: "2|Other error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
