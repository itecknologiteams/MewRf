from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.ControlWord import ControlWord

# 配置服务器/客户端模式参数
class Frame_0001_07(BaseFrame):
    # 参数 0 或者 0|1,9090 或者 1|2,192.168.1.1 & 3,9090
    def __init__(self, *data):
        try:
            super().__init__()
            self._CW = ControlWord()
            self._CW._CW_8_11 = "0001"
            self._CW._CW_MID = 0x07
            self._Data_Len = 0
            self.listData = bytearray()
            if data:
                strParam = data[0].rstrip("|").split("|")
                if len(strParam) == 1: # 只是切换模式不设置参数
                    self.listData.append(int(strParam[0]))
                elif len(strParam) == 2: # 设置参数伴随着模式切换
                    self.listData.append(int(strParam[0]))
                    if strParam[0] == "0": # 服务器模式下TCP端口号
                        varParam = strParam[1].rstrip(",").split(",")
                        self.listData.append(0x01)
                        self.listData.extend(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(int(varParam[1]))))
                    elif strParam[0] == "1":
                        varParam = strParam[1].rstrip("&").split("&")
                        for item in varParam:
                            strItem = item.rstrip(",").split(",")
                            if strItem[0].strip()=="2": # 设置客户端模式下服务器IP
                                self.listData.append(0x02)
                                for ipItem in strItem[1].rstrip(".").split(".") :
                                    aaa = int(ipItem)
                                    bbb = bytearray([aaa]) # 果然还是要转回成负数
                                    self.listData.extend(bbb)
                            elif strItem[0].strip()=="3": # 设置客户端模式下服务器端口
                                self.listData.append(0x03)
                                self.listData.extend(Helper_String.BytesToArraylist(Helper_String.GetReverseU16(int(strItem[1]))))
                            elif strItem[0].strip() == "162":  # 设置客户端模式下服务器IP
                                self.listData.append(0xA2)
                                sendData = bytes(strItem[1],'utf-8')
                                self.listData.append((len(sendData) >> 8) & 0xff)
                                self.listData.append(len(sendData) & 0xff)
                                # 获取数据内容
                                self.listData.extend(Helper_String.BytesToArraylist(sendData))
                            else:
                                raise Exception("01")
                else:
                    raise Exception("00")


                self._Data = Helper_String.ArraylisttoBytes(self.listData)
                self._Data_Len = len(self._Data)

        except Exception as e:
            print("Frame_0001_07(),Error!" + str(e))


    DIC_RESPONSE_CODE = {0: "0|OK",
                         1: "1|Error"}

    def GetReturnData(self):
        return self.DIC_RESPONSE_CODE.get(self._Data[0])

