from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 获取输出字符格式
class Frame_0001_57(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x57
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_57(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        # 0|1|0|00022323|00|00|00022424
        rt = ""
        if len(self._Data) > 0:
            for i in range(0,len(self._Data)):
                if i < 3:
                    rt += str(self._Data[i]) + "|"
                else:
                    if i == self._Data[4] + 5:
                        rt += "|" + str(self._Data[i]) + "|"
                    elif i == self._Data[4] + 6:
                        rt += str(self._Data[i]) + "|"
                    elif i == self._Data[4] + 9 + self._Data[self._Data[4] + 8]: # 可选参数  两个边长的长度 + 9 及为可选参数
                        rt += "|1," + Helper_String.ByteToString([self._Data[i + 1], self._Data[i + 2]]) + Helper_String.ByteToString([self._Data[i + 3]])
                        break
                    else:
                        temp = str(Helper_String.PrintHexStringByte(self._Data[i])).upper()
                        rt += temp if len(temp) == 2 else "0" + str(temp)
        return  rt
