from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置读写器自动空闲模式
class Frame_0010_0D(BaseFrame):
    #  0~255 | 1,0~65535
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x0D
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                strParam = data[0].rstrip("|").split("|")
                self.listData.append(int(strParam[0]))
                if len(strParam) == 2:
                    varParam = strParam[1].rstrip(",").split(",")
                    self.listData.append(int(varParam[0]))
                    self.listData.extend(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(int(varParam[1]))))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_0D(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1 | Mode parameter error",
                         2: "2|Other parameter error",
                         3: "3|Save failure"
                         }
    #  0~255 | 0~255 |  0~255 | 0~255
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])