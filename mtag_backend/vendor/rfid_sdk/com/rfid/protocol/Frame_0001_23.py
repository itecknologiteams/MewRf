from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 设置白名单动作参数
class Frame_0001_23(BaseFrame):
    # 参数: 继电器号|报警时间|输出功能开关|白名单功能数据类型
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x23
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                arr_Param = data[0].rstrip("|").split("|")
                for i in range(0,len(arr_Param)):
                    if i == 1:
                        self.listData.append(data[0][0:2])
                        self.listData.append(data[0][2:4])
                    else:
                        self.listData.append(arr_Param[i])
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_23(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    # 查询返回0为关闭状态，1为开启状态
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
