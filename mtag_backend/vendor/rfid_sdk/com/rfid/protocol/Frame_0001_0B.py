from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


class Frame_0001_0B(BaseFrame):
    def __init__(self,*data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x0B
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                arrParam = data[0].rstrip("|").split("|", -1)
                if len(arrParam) >= 4:
                    self.listData.append(int(arrParam[0]) & 0xff)
                    self.listData.append(int(arrParam[1]) & 0xff)
                    bData = Helper_String.hexStringToBytes(arrParam[2])
                    if arrParam[2] == "":
                        bData = Helper_String.hexStringToBytes("0")
                    self.listData.extend(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(len(bData))))
                    self.listData.extend(Helper_String.BytesToArraylist(bData))
                    self.listData.append(int(arrParam[3]) & 0xff)
                if len(arrParam) == 5:
                    varParams = arrParam[4].rstrip("&").split("&", -1)
                    for item in varParams:
                        varParam = item.rstrip(",").split(",", -1)
                        if varParam[0] == "1":
                            self.listData.append(0x01)
                            self.listData.extend(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(varParam[1])))
                        elif varParam[0] == "2":
                            self.listData.append(0x02)
                            self.listData.append(int(varParam[1]) & 0xff)
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)


        except Exception as e:
            raise RuntimeError("Frame_0001_0B(),Error!" + str(e))

    # 返回结果字典
    DIC_RESPONSE_CODE = { 0: "0|OK",
          1: "1|The port parameter is not supported in hardware of reader",
          2: "2|parameter miss"}


    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])

