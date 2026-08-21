from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 查询读写器WIFI连接信息
class Frame_0001_34(BaseFrame):
    # 查询WiFi连接状态
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x34
            self._Data_Len = 0
        except Exception as e:
            raise RuntimeError("Frame_0001_34(),Error!" + str(e))

    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Not supports"}

    def GetReturnData(self):
        ret = "-1|error"
        if self._Data != None:
            ulen = Helper_String.GetU16ByBytes(self._Data, 0)
            v_data = [0 for x in range(0,ulen)]
            Helper_Protocol.arrayCopy(self._Data, 2, v_data, 0, len(v_data))
            data = " "
            try :
                data = chr(v_data)
            except Exception as e:
                raise RuntimeError("Frame_0001_34(),Error!" + str(e))
            ret = data.rstrip('\n')
        return ret
