from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 请求接收到WIFI热点数据包
class Frame_0001_32(BaseFrame):

    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x32
            self._Data_Len = 0
            if data:
                self.listData = bytearray()
                self.listData.extend(Helper_String.BytesToArraylist(Helper_Protocol.ReverseLongToU32Bytes(data[0])))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)
        except Exception as e:
            raise RuntimeError("Frame_0001_32(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Not supports"}

    def GetReturnData(self):
        rt = ""
        index_data = bytearray(4)
        Helper_Protocol.arrayCopy(self._Data, 0, index_data, 0, 4)
        rt = Helper_String.ByteToString(index_data)
        v_data = bytearray(len(self._Data)-4)
        Helper_Protocol.arrayCopy(self._Data, 4, v_data, 0, len(v_data))

        vdata = ""
        try:
            vdata = chr(v_data)
        except Exception as e:
            raise RuntimeError("Frame_0001_32(),Error!" + str(e))
        rt += vdata
        return rt
