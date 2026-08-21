from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置Wifi网卡的IP
class Frame_0001_35(BaseFrame):
    # 192.168.1.8|255.255.255.0|192.168.1.1
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x35
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                strParam = data[0].rstrip("|").split("|")
                if (len(strParam) == 3) or (len(strParam) == 4):
                    for i in range(0,3):
                        item = strParam[i]
                        byteParam = item.rstrip(".").split(".")
                        if len(byteParam) == 4:
                            for bItem in byteParam:
                                self.listData.append(int(bItem) & 0xff)
                        else:
                            raise Exception("01")
                    if len(strParam) == 4:
                        appendParam = strParam[3].rstrip("&").split("&")
                        for i in range(0,len(appendParam)):
                            pidParam = appendParam[i].rstrip(",").split(",")
                            self.listData.append(int(pidParam[0]) & 0xff)
                            value  = int(pidParam[0])
                            if value == 0x01:
                                byteParam = pidParam[1].rstrip(".").split(".")
                                if len(byteParam) == 4:
                                    for bItem in byteParam:
                                        self.listData.append(int(bItem) & 0xff)
                                else:
                                    raise Exception("01")
                            elif value == 0x60:
                                self.listData.append(int(pidParam[1]) & 0xff)
                            elif value == 0x61:
                                ipv6 = pidParam[1].rstrip(":").split(":")
                                for bItem in ipv6:
                                    byteStr = Helper_String.hexStringToBytes(bItem)
                                    for item in  byteStr:
                                        self.listData.append(item)
                            elif value == 0x62:
                                self.listData.append(int(pidParam[1]) & 0xff)
                            elif value == 0x63:
                                gateway = pidParam[1].rstrip(":").split(":")
                                for bItem in gateway:
                                    byteStr = Helper_String.hexStringToBytes(bItem)
                                    for item in byteStr:
                                        self.listData.append(item)
                            elif value == 0x64:
                                dns = pidParam[1].rstrip(":").split(":")
                                for bItem in dns:
                                    byteStr = Helper_String.hexStringToBytes(bItem)
                                    for item in byteStr:
                                        self.listData.append(item)
                    else:
                        raise Exception("00")
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_35(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Reader IP parameter error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])
