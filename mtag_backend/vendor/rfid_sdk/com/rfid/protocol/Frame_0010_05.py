from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


# 配置读写器工作频率
class Frame_0010_05(BaseFrame):
    # 频率自动设置,0~255|0,7,15
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x05
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                strParam = data[0].rstrip("|").split("|")
                self.listData.append(int(strParam[0]))
                if len(strParam) == 2:
                    varParam = strParam[1].rstrip(",").split(",")
                    if len(varParam) > 0:
                        self.listData.append(0x01)
                        s = Helper_String.GetReverseU16(len(varParam))
                        ss = Helper_String.BytesToArraylist(s)
                        self.listData.extend(ss)
                    for item in varParam:
                        self.listData.append(int(item))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_05(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The channel number is not in the current frequency band",
                         2: "2|Invalid number of frequency points",
                         3: "3|Other parameter error",
                         4: "4|Save failure"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])