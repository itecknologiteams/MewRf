from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

class Frame_0010_10(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x10
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                arrParam = data[0].rstrip("|").split("|")
                self.listData.append(int(arrParam[0]))
                dataLen += 1
                self.listData.append(int(arrParam[1]))
                dataLen += 1
                if len(arrParam) == 3:
                    varParams = arrParam[2].rstrip("&").split("&")
                    for item in varParams:
                        tempItem = item.rstrip(",").split(",")
                        if tempItem[0] == "1" or tempItem[0] == "13" or tempItem[0] == "14":
                            self.listData.append(int(tempItem[0]))
                            if len(tempItem[1]) % 2 != 0:
                                tempItem[1] = tempItem[1] + "0"
                            dataLen += 1
                            tempItem[1] = Helper_String.PrintHexStringByteSum(Helper_Protocol.ReverseIntToU16Bytes(int(len(tempItem[1]) / 2))) + tempItem[1]
                            bParam = Helper_String.hexStringToBytes(tempItem[1])
                            self.listData.extend(Helper_String.BytesToArraylist(bParam))
                            dataLen += len(bParam)
                        else:
                            self.listData.append(int(tempItem[0]))
                            dataLen += 1
                            bParam = Helper_String.hexStringToBytes(tempItem[1])
                            self.listData.extend(Helper_String.BytesToArraylist(bParam))
                            dataLen += len(bParam)
                self._Data = bytearray(dataLen)
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0010_10(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Ant Port Parameter Error",
                         2: "2|Select Read Parameter Error",
                         3: "3|TID Read Parameter Error",
                         4: "4|Userdata Read Parameter Error",
                         5: "5|Reserve Read Parameter Error",
                         6: "6|Other Parameter Error"}

    # 1,0~65535 & 2,0~255
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])