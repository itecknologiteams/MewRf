from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


class Frame_0010_0B(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x0B
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                strParam = data[0].rstrip("&").split("&")
                for item in strParam:
                    varItem = item.rstrip(",").split(",")
                    self.listData.append(int(varItem[0]))
                    self.listData.append(int(varItem[1]))
                    dataLen += 2
                self._Data = [0 for x in range(0,dataLen)]
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_0B(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The reader does not support the baseband rate",
                         2: "2|Q value parameter error",
                         3: "3|Session parameter error",
                         4: "4|Inventory parameter error",
                         5: "5|Other parameter error",
                         6: "6|Save failure"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])


