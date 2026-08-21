from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 发射载波
class Frame_0101_00(BaseFrame):
    # "1|1"
    def __init__(self,*data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0101"
            self._CW._CW_MID = 0x00
            self._Data_Len = 0
            if len(data) == 2:
                self.listData = bytearray()
                dataLen = 0
                self.listData.append(int(data[0]) & 0xff)
                dataLen += 1
                self.listData.append(int(data[1]))
                dataLen += 1
                if (data[0] & 0xffffff00) != 0:
                    self.listData.append(0x01)
                    dataLen += 1
                    self.listData.append((int(data[0]) >> 16) & 0xff)
                    dataLen += 1
                    self.listData.append((int(data[0]) >> 8) & 0xff)
                    dataLen += 1
                self._Data = bytearray(dataLen)
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)
            elif len(data) == 1:
                strParam = data[0].rstrip("|").split("|")

                self.listData = bytearray()
                if int(strParam[0]) > 127:
                    self.listData.append(int(strParam[0]) - 256)
                else:
                    self.listData.append(int(strParam[0]))
                    self.listData.append(int(strParam[1]))
                if len(strParam) == 3:
                    varParams = strParam[2].rstrip("&").split("&")
                    for item in varParams:
                        tempItem = item.rstrip(",").split(",")
                        if tempItem[0] == "1":
                            self.listData.append(int(tempItem[0]))
                            self.listData.extend(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(int(tempItem[1]))))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0101_00(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|System error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
