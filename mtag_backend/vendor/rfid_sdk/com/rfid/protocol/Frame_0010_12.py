from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 锁定标签
class Frame_0010_12(BaseFrame):
    # 天线端口|锁操作区域|锁操作类型|0x01,选择写入参数 & 0x02,标签访问密码
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x12
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                arrParam = data[0].rstrip("|").split("|")
                if len(arrParam) >= 3: # 必选参数
                    self.listData.append(int(arrParam[0]))
                    dataLen += 1
                    self.listData.append(int(arrParam[1]))
                    dataLen += 1
                    self.listData.append(int(arrParam[2]))
                    dataLen += 1
                if len(arrParam) == 4: # 可选参数
                    dic_Data = super().GetOptionalParam(arrParam[3])
                    for key, value in dic_Data.items():
                        swKey = key & 0xFF
                        bValue = value
                        if swKey == 1:
                            self.listData.append(0x01)
                            dataLen += 1
                            self.listData.extend(Helper_Protocol.ReverseIntToU16Bytes(len(bValue)))
                            dataLen += 2
                            self.listData.extend(bValue)
                            dataLen += len(bValue)
                        elif swKey == 2:
                            self.listData.append(0x02)
                            dataLen += 1
                            self.listData.extend(bValue)
                            dataLen += len(bValue)
                        elif swKey == 3:
                            self.listData.append(0x03)
                            dataLen += 1
                            self.listData.extend(bValue)
                            dataLen += len(bValue)

                self._Data = bytearray(dataLen)
                Helper_Protocol.arrayCopy(self.listData, 0, self._Data, 0, len(self._Data))
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0010_12(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The antenna port parameter is incorrect",
                         2: "2|Select parameter error",
                         3: "3|Write parameter error",
                         4: "4|CRC check error",
                         5: "5|Power shortage",
                         6: "6|Data area overflow",
                         7: "7|The data area is locked",
                         8: "8|Access password error",
                         9: "9|Other tag error",
                         10: "10|Tag lost",
                         11: "11|Instruction error"
                         }

    # 1,0~65535 & 2,0~255
    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])