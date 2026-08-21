from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 设置读写器NTP
class Frame_0001_64(BaseFrame):
    # 开关|ip地址/主机名称
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x64
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                strParam = data[0].rstrip("|").split("|")
                self.listData.append(int(strParam[0]))
                if len(strParam) == 2:
                    byteParam = strParam[1].rstrip(".").split(".")
                    if len(byteParam) == 4:
                        self.listData.append(0x01)
                        for bItem in byteParam:
                            self.listData.append(int(bItem))
                    else:
                        self.listData.append(0xA1)
                        sendData = str(strParam[1], encoding='utf-8')
                        self.listData.append((len(sendData) >> 8) & 0xff)
                        self.listData.append((len(sendData)) & 0xff)
                        # 获取数据内容
                        self.listData.append(Helper_String.BytesToArraylist(sendData))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_64(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])