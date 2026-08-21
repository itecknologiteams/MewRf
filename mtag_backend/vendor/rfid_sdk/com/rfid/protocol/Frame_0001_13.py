from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置串口参数
class Frame_0001_13(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x13
            self._Data_Len = 0
            self.listData = bytearray()
            if data:
                strParam = data[0].rstrip("-").split("-")
                for item in  strParam:
                    self.listData.extend(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(item)))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0001_13(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|MAC parameter error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
