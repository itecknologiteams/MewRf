from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询DHCP
class Frame_0001_30(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x30
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_30(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|DHCP Off",
                         1: "1|DHCP On"}

    # 查询返回0为关闭状态，1为开启状态
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
