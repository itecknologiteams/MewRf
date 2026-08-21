from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 写国标标签
class Frame_0010_51(BaseFrame):
    # 天线端口|数据区|字起始地址|数据内容|0x01,选择写入参数 & 0x02,标签访问密码
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x51
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                dataLen = 0
                arrParam = data[0].rstrip("|").split("|", -1)
                if len(arrParam) >= 4: # 必选参数
                    self.listData.append(int(arrParam[0]) & 0xff)
                    self.listData.append(int(arrParam[1]) & 0xff)
                    self.listData.append(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(arrParam[2])))
                    tempData = Helper_String.hexStringToBytes(arrParam[3])
                    self.listData.append(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(len(tempData))))
                    self.listData.append(Helper_String.BytesToArraylist(tempData))
                elif len(arrParam) == 5: # 可选参数
                    dic_Data = super().GetOptionalParam(arrParam[4])
                    for key,value in dic_Data:
                        if key == 0x01:
                            self.listData.append(0x01)
                            temp = value
                            data1 = Helper_String.GetReverseU16(len(temp))
                            self.listData.append(Helper_String.BytesToArraylist(data1))
                            self.listData.append(Helper_String.BytesToArraylist(value))
                        elif key == 0x02:
                            self.listData.append(0x02)
                            self.listData.append(Helper_String.BytesToArraylist(value))
                        elif key == 0x03:
                            self.listData.append(0x03)
                            self.listData.append(Helper_String.BytesToArraylist(value))
                        elif key == 0xf0:
                            self.listData.append(0xf0)
                            self.listData.append(Helper_String.BytesToArraylist(value))
                        else:
                            self.listData.append(key)
                            self.listData.append(Helper_String.BytesToArraylist(value))

                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_51(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The antenna pore parameter error",
                         2: "2|Select read parameter error",
                         3: "3|Write parameter error",
                         4: "4|CRC check error",
                         5: "5|Power shortage",
                         6: "6|Data area overflow",
                         7: "7|The data area is locked",
                         8: "8|Access password error",
                         9: "9|Insufficient permissions",
                         10: "10|Authentication failed",
                         11: "11|Other tag error",
                         12: "12|Tag lost",
                         13: "13|Instruction error"
                         }

    def GetReturnData(self):
        if len(self._Data) == 1:
            return self.DIC_RESPONSE_CODE.get(self._Data[0])
        elif len(self._Data) == 4:
            return self.DIC_RESPONSE_CODE.get(self._Data[0]) + "|" + Helper_String.GetU16ByBytes(self._Data, 2)
        return super().GetReturnData()