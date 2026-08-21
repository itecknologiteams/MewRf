from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置EPC扩展基带参数
class Frame_0010_E0(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0xE0
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                array_param = data[0].rstrip("&").split("&")
                for i in range(0,len(array_param)):
                    array_Single = array_param[i].rstrip(",").split(",")
                    self.listData.append(int(array_Single[0]))
                    self.listData.extend(Helper_String.hexStringToBytes(array_Single[1]))
                self._Data = bytearray(len(self.listData))
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_E0(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Parameter not support",
                         2: "2|IMJ parameter Error",
                         3: "3|DNQ parameter Error",
                         4: "4|ANT parameter Error",
                         5: "5|ANT2 parameter Error",
                         6: "6|Save failed"}
    # 查询结果 255|255
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(int(self._Data[0]))