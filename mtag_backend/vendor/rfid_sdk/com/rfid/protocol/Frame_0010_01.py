from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 设置天线功率
class Frame_0010_01(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x01
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                array_param = data[0].rstrip("&").split("&")
                for i in range(0,len(array_param)):
                    array_Single = array_param[i].rstrip(",").split(",")
                    self.listData.append(int(array_Single[0]))
                    self.listData.append(int(array_Single[1]))
                    dataLen += 2
                self._Data = bytearray(dataLen)
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_01(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The port parameter is not supported in hardware of reader",
                         2: "2|The power parameter is not supported in hardware of reader",
                         3: "3|Save failure"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])