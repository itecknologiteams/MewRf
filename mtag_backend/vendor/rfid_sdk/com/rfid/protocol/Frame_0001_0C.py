from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询GPI触发参数
class Frame_0001_0C(BaseFrame):
    # param GPI端口号
    def __init__(self,*data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x0C
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                self.listData.append(int(data[0]))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_0C(),Error!" + str(e))

    # 0 | 触发绑定的指令 | 0 | U16
    def GetReturnData(self):
        rt = ""
        dataindex = 0
        rt += str(self._Data[dataindex]) + "|"
        dataindex += 1
        ulen = Helper_String.GetU16ByBytes(self._Data, dataindex)
        dataindex += 2
        cmdByte = [0 for x in range(0,ulen)]
        Helper_Protocol.arrayCopy(self._Data, dataindex, cmdByte, 0, len(cmdByte))
        dataindex += ulen
        rt += Helper_String.ByteToString(cmdByte) + "|"
        rt += str(self._Data[dataindex]) + "|"
        dataindex += 1
        rt += str(Helper_String.GetU16ByBytes(self._Data, 4 + ulen))
        dataindex += 2
        if dataindex < len(self._Data) : # 触发条件不停止时IO电平变化上传开关
            rt += "|" + str(self._Data[dataindex])
        return rt

