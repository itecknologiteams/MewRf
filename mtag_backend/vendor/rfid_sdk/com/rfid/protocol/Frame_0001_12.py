from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 连接状态消息确认
class Frame_0001_12(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x12
            self._Data_Len = 0
            self.listData = bytearray()
            if data:
                self.listData.extend(Helper_String.BytesToArraylist(self.GetReverseS32(data[0])))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_12(),Error!" + str(e))

    def GetReturnData(self):
        return self.GetS32ByBytes(self._Data, 0)

    def GetS32ByBytes(self, data, startIndex):
        rt = 0
        try:
            tempByte = [0 for x in range(0,4)]
            Helper_Protocol.arrayCopy(data, startIndex, tempByte, 0, 4)
            rt = self.ByteArrayToInt(tempByte)
        except Exception as e:
            raise RuntimeError("Frame_0001_11(),Error!" + str(e))
        return rt

    def ByteArrayToInt(self,b):
        return b[3] & 0xFF | (b[2] & 0xFF) << 8 | (b[1] & 0xFF) << 16 | (b[0] & 0xFF) << 24

    def GetReverseS32(self, data):
        rt = bytearray(4)
        rt = self.IntToBytes(data)
        rt = self.ArrayReverse(rt)
        return rt

    def IntToBytes(self, data):
        return bytearray([data & 0x00FF, (data & 0xFF00) >> 8, (data & 0xFF0000) >> 16,(data & 0xFF000000) >> 24])

    def ArrayReverse(self, data):
        new_array = bytearray(len(data))
        for i in range(0, len(data)):  # 反转后数组的第一个元素等于源数组的最后一个元素：
            new_array[i] = data[len(data) - i - 1]
        return new_array