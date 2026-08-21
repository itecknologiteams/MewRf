from com.rfid.helper.Helper_Byte import Helper_Byte
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 最小发射功率|最大发射功率|天线数目|频段列表|RFID协议列表
class Frame_0010_00(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0010"
            self._CW._CW_MID = 0x00
            self._Data_Len = 0
            if data:
                super().__init__(data)
        except Exception as e:
            raise RuntimeError("Frame_0010_00(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        rt = ""
        copyIndex = 0
        rt += str(self._Data[copyIndex]) + "|"
        copyIndex += 1
        rt += str(self._Data[copyIndex]) + "|"
        copyIndex += 1
        rt += str(self._Data[copyIndex]) + "|"
        copyIndex += 1
        temp_Byte = bytearray(2)
        Helper_Protocol.arrayCopy(self._Data, copyIndex, temp_Byte, 0, 2)
        len1 = Helper_Byte.byte2Short(temp_Byte)
        copyIndex += 2
        for i in range(0,len1):
            rt += str(self._Data[copyIndex]) + ","
            copyIndex += 1
        if rt.endswith(","):			# 去掉尾部","
            rt = rt[0: len(rt) - 1]
        rt += "|"
        Helper_Protocol.arrayCopy(self._Data, copyIndex, temp_Byte, 0, 2)
        len2 = Helper_Byte.byte2Short(temp_Byte)
        copyIndex += 2
        for i in range(0,len2):
            rt += str(self._Data[copyIndex]) + ","
            copyIndex += 1

        if rt.endswith(","):  # 去掉尾部","
            rt = rt[0: len(rt) - 1]
        return rt