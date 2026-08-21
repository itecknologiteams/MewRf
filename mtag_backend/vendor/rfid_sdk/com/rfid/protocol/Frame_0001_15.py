from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置读写器RS485设备地址
class Frame_0001_15(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x15
            self._Data_Len = 0
            self.listData = bytearray()
            if data:
                arr_Param = data[0].rstrip("|").split("|", -1)
                if int(arr_Param[0]) > 127:
                    self.listData.append(int(arr_Param[0]) - 256)
                else:
                    self.listData.append(int(arr_Param[0]))
                    if len(arr_Param) == 2:
                        varParam = arr_Param[1].rstrip(",").split(",", -1)
                        if varParam[0] == "1":
                            self.listData.append(0x01)
                            self.listData.append(int(varParam[1]))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0001_15(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Other error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
