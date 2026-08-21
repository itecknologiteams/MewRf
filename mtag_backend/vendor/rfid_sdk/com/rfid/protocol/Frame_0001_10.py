from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置UTC
class Frame_0001_10(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x10
            self._Data_Len = 0
            listData = bytearray()
            if data:
                arrParam = data[0].rstrip(".").split(".", -1)
                if len(arrParam) == 2:
                    listData.extend(Helper_String.BytesToArraylist(self.GetReverseS32(int(arrParam[0]))))
                    listData.extend((Helper_String.BytesToArraylist(self.GetReverseS32(int(arrParam[1]) * 1000))))
                self._Data = Helper_String.ArraylisttoBytes(listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0001_10(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|RTC error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])

    def GetReverseS32(self,data):
        rt = bytearray(4)
        rt = self.IntToBytes(data)
        rt = self.ArrayReverse(rt)
        return rt

    def IntToBytes(self,data):
        return bytearray([data & 0x00FF,(data & 0xFF00)>>8,(data & 0xFF0000)>>16,(data & 0xFF000000)>>24])

    def ArrayReverse(self,data):
        new_array = bytearray(len(data))
        for i in range(0,len(data)): # 反转后数组的第一个元素等于源数组的最后一个元素：
            new_array[i] = data[len(data) - i - 1]
        return new_array
