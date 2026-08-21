from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置DHCP
class Frame_0001_2F(BaseFrame):
    # 参数DHCP开关，0为关闭，1为打开
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x2F
            self._Data_Len = 0
            self.listData = bytearray()
            if data:
                self.listData.append(int(data[0]))
            self._Data = Helper_String.ArraylisttoBytes(self.listData)
            self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0001_2F(),Error!" + str(e))


    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])

