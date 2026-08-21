from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

class Frame_0001_1E(BaseFrame):
    # 设置蜂鸣器控制
    #  @param 0关闭，1开启
    def __init__(self,*data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x1E
            self._Data_Len = 0
            if data:
                self.listData = bytearray([int(data[0])])
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_1E(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}
    
    # 查询返回0为有缓存数据，1为无缓存数据，2数据返回结束
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])

