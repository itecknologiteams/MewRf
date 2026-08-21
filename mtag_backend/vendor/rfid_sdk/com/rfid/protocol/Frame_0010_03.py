from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 设置读写器频段
class Frame_0010_03(BaseFrame):
    # 0，国标920~925MHz 1，国标840~845MHz 2，国标840~845MHz和920~925MHz 3，FCC，902~928MHz ETSI，866~868MHz
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x03
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                b_param = bytearray([data[0]])
                self.listData.extend(b_param)
                self._Data = bytearray(1)
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_03(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The frequency band parameter is not supported in hardware of reader",
                         2: "2|Save failure"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])