from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

class Frame_0010_20(BaseFrame):
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x20
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                arrParam = data[0].rstrip("|").split("|")
                if len(arrParam) >= 2: # 必选参数
                    self.listData.append(int(arrParam[0]))
                    dataLen += 1
                    self.listData.append(Helper_Protocol.ReverseIntToU16Bytes(int(arrParam[1])))
                    dataLen += 2
                if len(arrParam) == 3: # 可选参数
                    arrParam = arrParam[2].rstrip("&").split("&")
                    for i in range(0,len(arrParam)):
                        item = arrParam[i].rstrip(",").split(",")
                        if item[0] == "1":
                            self.listData.append(0x01)
                            dataLen += 1
                            tempData = Helper_String.hexStringToBytes(item[1])
                            self.listData.append(Helper_Protocol.ReverseIntToU16Bytes(len(tempData)))
                            dataLen += 2
                            self.listData.append(tempData)
                        elif item[0] == "2":
                            self.listData.append(0x02)
                            dataLen += 1
                            byteArray = Helper_String.hexStringToBytes(item[1])
                            self.listData.append(byteArray)
                            dataLen += len(byteArray)
                self._Data = [0 for x in range(0,dataLen)]
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0010_20(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|Success",
                         1: "1|Antenna port parameter error",
                         2: "2|Wrong parameter selection",
                         3: "3|Wrong parameter Untraceable",
                         4: "4|CRC check error",
                         5: "5|Power shortage",
                         6: "6|Password error",
                         7: "7|Unsupported instructions",
                         8: "8|Other label errors",
                         9: "9|Label loss",
                         10: "10|Reader failed to send instructions"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])