
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 设置输出字符格式
class Frame_0001_56(BaseFrame):
    # 参数: 特殊格式输出开关|数据输出格式|输出数据类型|数据帧头|保留|保留|数据帧尾
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x56
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                arr_Param = data[0].split('|')
                for i in range(0,len(arr_Param)):
                    if i == 3 or i == 6 :
                        self.listData.extend(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(arr_Param[i])))
                        continue
                    elif i == 7 :
                        tempItem = arr_Param[i].rstrip(",").split(",")
                        self.listData.append(int(tempItem[0]))
                        self.listData.extend(Helper_String.BytesToArraylist( Helper_String.hexStringToBytes(tempItem[1])))
                        continue
                    self.listData.append(int(arr_Param[i]))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_56(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
