from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 设置心跳检测次数
class Frame_0001_48(BaseFrame):
    # 参数: 心跳包发送间隔|心跳包检测次数
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x48
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                arr_Param = data[0].rstrip("|").split("|")
                for i in range(0,len(arr_Param)):
                    aa = Helper_String.GetReverseU16(arr_Param[i])
                    if len(aa) == 2:
                        self.listData.append(aa[0])
                        self.listData.append(aa[1])
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_48(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Param error",
                         2: "2|Save failed"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
