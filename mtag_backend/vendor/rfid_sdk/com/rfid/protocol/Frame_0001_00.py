from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord


class Frame_0001_00(BaseFrame):
    def __init__(self,*data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x00
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_00(),Error!" + str(e))

    def GetReturnData(self):
        rt = "V"
        if (self._Data[0] == 0 and self._Data[1] == 0): # 两位版本
            rt += str(self._Data[2]) + "." + str(self._Data[3])
        elif self._Data[0] == 0: # 三位版本
            rt += str(self._Data[1]) + "." + str(self._Data[2]) + "." + str(self._Data[3])
        else:   #四位版本
            rt += str(self._Data[0]) + "." + str(self._Data[1]) + "." + str(self._Data[2]) + "." + str(self._Data[3])
        copyIndex = 4
        ulen = Helper_String.GetU16ByBytes(self._Data, copyIndex)
        copyIndex += 2
        v_data = bytearray(ulen)
        Helper_Protocol.arrayCopy(self._Data, copyIndex, v_data, 0, len(v_data))
        readerName = ""
        try:
            readerName = v_data.decode("UTF-8")
        except Exception as e:
            raise RuntimeError("Frame_0001_00(),Error!" + str(e))

        rt += "|" + readerName
        copyIndex += len(v_data)

        time = Helper_String.GetU32ByBytes(self._Data, copyIndex)
        rt += "|" + str(time)

        return rt

