from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


class Frame_0001_33(BaseFrame):
    # "1111|1,123456&2,0&3,2"
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x33
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                strParam = data[0].rstrip("|").split("|")
                strParam[0] = "{:x}".format(strParam[0])
                nameStr = Helper_String.ByteToString(Helper_String.GetReverseU16((len(strParam[0]) / 2))) + strParam[0]
                self.listData.append(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(nameStr)))
                if len(strParam) == 2:
                    varpara = strParam[1].rstrip("&").split("&")
                    for item in varpara:
                        tempItem = item.rstrip(",").split(",")
                        if tempItem[0] == "1":
                            self.listData.append(0x01)
                            tempItem[1] = "{:x}".format(tempItem[1])
                            pwdStr = Helper_String.ByteToString(Helper_String.GetReverseU16(len(tempItem[1]) / 2)) + tempItem[1]
                            self.listData.append(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(pwdStr)))
                        elif tempItem[0] == "2":
                            self.listData.append(0x02)
                            self.listData.append(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(tempItem[1])))
                        elif tempItem[0] == "3":
                            self.listData.append(0x03)
                            self.listData.append(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(tempItem[1])))

                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_33(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
