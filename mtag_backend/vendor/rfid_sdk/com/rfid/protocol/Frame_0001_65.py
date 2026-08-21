from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 询读写器StateLED
class Frame_0001_65(BaseFrame):
    # 开关|1,时长
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x65
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                strParam = data[0].rstrip("|").split("|")
                self.listData.append(int(strParam[0]))
                if len(strParam) == 2:
                    varParam = strParam[1].rstrip("&").split("&", -1)
                    for item in varParam :
                        strItem = item.rstrip(",").split(",", -1)
                        if strItem[0].strip() == "1": # 设置客户端模式下服务器IP
                            self.listData.append(0x01)
                            self.listData.extend(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(int(strItem[1]))))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0001_65(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])


