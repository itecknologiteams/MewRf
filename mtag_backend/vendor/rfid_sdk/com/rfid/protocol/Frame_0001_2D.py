from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 设置读写器自检功能
class Frame_0001_2D(BaseFrame):
    # 参数 检测开关|检测ip地址
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x2D
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                strParam = data[0].rstrip("|").split("|")
                self.listData.append(strParam[0])
                if len(strParam) == 2:
                    byteParam = strParam[1].rstrip(".").split(".")
                    if len(byteParam) == 4:
                        for bItem in byteParam:
                            self.listData.append(int(bItem))
                    else:
                        raise Exception("01")
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_2D(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])

