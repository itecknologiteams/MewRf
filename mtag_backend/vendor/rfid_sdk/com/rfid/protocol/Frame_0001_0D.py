from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


class Frame_0001_0D(BaseFrame):
    # 返回结果字典
    DIC_RESPONSE_CODE = { 0: "0|OK",
          1: "1|hardware of reader does not support Wiegand access",
          2: "2|The Wiegand communication format does not support in the reader",
          3: "3|The data content does not support in the reader"}
    # 配置韦根通信参数
    # param 0|0|0
    def __init__(self,*data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x0D
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                arrParam = data[0].rstrip("|").split("|", -1)

                self.listData.append(arrParam[0])
                self.listData.append(arrParam[1])
                self.listData.append(arrParam[2])
                if len(arrParam) == 4 :
                    varParam = arrParam[3].rstrip(",").split(",")
                    if varParam[0] == "1":
                        self.listData.append(1)
                        self.listData.append(int(varParam[1]))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)


        except Exception as e:
            raise RuntimeError("Frame_0001_0D(),Error!" + str(e))




    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])

