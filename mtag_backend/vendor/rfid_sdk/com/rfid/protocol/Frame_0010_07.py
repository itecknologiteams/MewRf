from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


# 配置读写器天线 255|1,1-2-3-5-7&2,4-5-6  (兼容天线扩展功能)
class Frame_0010_07(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x07
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                array_Param = data[0].rstrip("|").split("|", -1)
                if len(array_Param) == 1: # 不带天线扩展
                    temp = int(array_Param[0])
                    # temp = temp if temp < 128 else temp - 256 # 大于128还要转回负数
                    self.listData.append(temp)
                elif len(array_Param) == 2:  # 带天线扩展，有可选参数
                    temp = int(array_Param[0])
                    # temp = temp if temp < 128 else temp - 256  # 大于128还要转回负数
                    self.listData.append(temp)

                    array_Param_Optional = array_Param[1].rstrip("&").split("&", -1) # 分离可选参数
                    if len(array_Param_Optional) > 0:
                        for item in array_Param_Optional: # 单可选参数处理
                            ID_Param = item.rstrip(",").split(",", -1)  # 可选参数ID及参数
                            if len(ID_Param) == 2:
                                if ID_Param[0] != "25":
                                    self.listData.append(ID_Param[0]) # 添加可选ID
                                    array_Optional = ID_Param[1].rstrip("-").split("-", -1)
                                    self.listData.extend(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(int(len(array_Optional))))) # 添加变长参数长度
                                    for item_Optional in array_Optional: # 添加选项列表
                                        self.listData.append(item_Optional)
                                else:
                                    self.listData.append(ID_Param[0])
                                    self.listData.extend(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(ID_Param[1])))

                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0010_07(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|The antenna port does not exist",
                         2: "2|Save failure"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])