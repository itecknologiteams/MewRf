from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 设置自定义编码
class Frame_0001_5F(BaseFrame):
    # 参数 0A0B|C0A80164
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x5F
            self._Data_Len = 0
            self.listData = bytearray()
            if data:
                sendData = bytes(data[0],'ascii')
                # 获取数据长度
                sendLen = len(sendData)
                hexStrLen = ("{:x}".format(sendLen)).rjust(4,'0')
                self.listData.append(int(hexStrLen[0:2], 16))
                self.listData.append(int(hexStrLen[2:4], 16))
                # 获取数据内容
                self.listData.extend(Helper_String.BytesToArraylist(sendData))
                arr_Param = data[0].rstrip("|").split("|")
                for item in arr_Param:
                    self.listData.extend(Helper_String.BytesToArraylist(Helper_String.hexStringToBytes(item)))
                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            raise RuntimeError("Frame_0001_5F(),Error!" + str(e))


    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0]);

