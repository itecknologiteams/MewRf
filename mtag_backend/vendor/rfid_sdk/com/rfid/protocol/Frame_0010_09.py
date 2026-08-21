from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


# 配置标签上传参数
class Frame_0010_09(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x09
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                strParam = data[0].rstrip("&").split("&")
                for item in strParam:
                    varItem = item.rstrip(",").split(",")
                    if int(varItem[0]) == 1:
                        self.listData.append(0x01)
                        dataLen += 1
                        self.listData.extend(Helper_Protocol.ReverseIntToU16Bytes(int(varItem[1])))
                        dataLen += 2
                    elif int(varItem[0]) == 2:
                        self.listData.append(0x02)
                        dataLen += 1
                        self.listData.append(int(varItem[1]))
                        dataLen += 1
                    elif int(varItem[0]) == 3:
                        self.listData.append(0x03)
                        dataLen += 1
                        self.listData.append(int(varItem[1]))
                        dataLen += 1
                self._Data = bytearray(dataLen)
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0010_09(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Parameter error",
                         2: "2|Save failure"}

    # 1,0~65535 & 2,0~255
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])