
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 设置输出字符格式
class Frame_0001_55(BaseFrame):
    # 参数: 特殊格式输出开关|数据输出格式|输出数据类型|数据帧头|保留|保留|数据帧尾
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x55
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_55(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return str(self._Data[0])
