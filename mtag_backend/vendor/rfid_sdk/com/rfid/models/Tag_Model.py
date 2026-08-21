import math
import time

from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String

# 标签数据模型
class Tag_Model:
    CustomID = ""
    def __init__(self, type, *data):
        self._ReaderName = ""
        self._ReaderSN = ""
        self._PC = None
        self._EPC = None
        self._TagType = "6C"
        self._ANT_NUM = 0
        self._ANT1_COUNT = 0
        self._ANT2_COUNT = 0
        self._ANT3_COUNT = 0
        self._ANT4_COUNT = 0
        self._ANT5_COUNT = 0
        self._ANT6_COUNT = 0
        self._ANT7_COUNT = 0
        self._ANT8_COUNT = 0
        self._ANT9_COUNT = 0
        self._ANT10_COUNT = 0
        self._ANT11_COUNT = 0
        self._ANT12_COUNT = 0
        self._ANT13_COUNT = 0
        self._ANT14_COUNT = 0
        self._ANT15_COUNT = 0
        self._ANT16_COUNT = 0
        self._ANT17_COUNT = 0
        self._ANT18_COUNT = 0
        self._ANT19_COUNT = 0
        self._ANT20_COUNT = 0
        self._ANT21_COUNT = 0
        self._ANT22_COUNT = 0
        self._ANT23_COUNT = 0
        self._ANT24_COUNT = 0
        self._TotalCount = 1
        self._RSSI = 0
        self._RSSI_dB = 0
        self._Result = 0
        self._TID = ""
        self._UserData = ""
        self._RsvdData = ""
        self._IsContinue = 0
        self._SerialNo = None
        self._Bag = ""
        self._UTC = None
        self._Frequency = 0
        self._Phase = 0
        self._ReadTime = ""
        self._EpcData = ""
        self._EMSensorData = ""
        self._RFSensorData = ""
        self._RFRSSIData = ""
        self._RFCaliberateTemperatureData = ""
        self._CABSensorData = ""
        self._G2V2Challenge = ""
        self._G2V2Data = ""
        self._LTU32SensorData = ""
        self._NXPBrandIdentify = ""
        self._EASFlag = 0
        self._CustomID = ""
        if type == 0:
            self.Init6C(data[0])
        elif type == 1:
            self.Init6B(data[0])
        elif type == 2:
            self.InitGB(data[0])

    # 解析6C标签
    def Init6C(self, dataParam):
        try:
            if self.CustomID != None and self.CustomID !="":
                self._CustomID = self.CustomID
            param = dataParam
            copyIndex = 0
            dataLen = Helper_Protocol.U16BytesToInt(param, copyIndex)
            copyIndex += 2
            if dataLen > 0:
                b_EPC = bytearray(dataLen)
                Helper_Protocol.arrayCopy(param, copyIndex, b_EPC, 0, len(b_EPC))
                self._EPC = Helper_String.PrintHexStringByteSum(b_EPC)  # 获得EPC值
                copyIndex += len(b_EPC)

            b_PC = bytearray(2)
            Helper_Protocol.arrayCopy(param, copyIndex, b_PC, 0, 2)
            self._PC = Helper_String.PrintHexStringByteSum(b_PC)  # 获得PC值
            copyIndex += 2
            self._ANT_NUM = param[copyIndex]  # 读取天线号
            copyIndex += 1

            if self._ANT_NUM == 1:
                self._ANT1_COUNT  = 1
            if self._ANT_NUM == 2:
                self._ANT2_COUNT = 2
            if self._ANT_NUM == 3:
                self._ANT3_COUNT  = 3
            if self._ANT_NUM == 4:
                self._ANT4_COUNT = 4
            if self._ANT_NUM == 5:
                self._ANT5_COUNT = 5
            if self._ANT_NUM == 6:
                self._ANT6_COUNT = 6
            if self._ANT_NUM == 7:
                self._ANT7_COUNT = 7
            if self._ANT_NUM == 8:
                self._ANT8_COUNT = 8
            if self._ANT_NUM == 9:
                self._ANT9_COUNT = 9
            if self._ANT_NUM == 10:
                self._ANT10_COUNT = 10
            if self._ANT_NUM == 11:
                self._ANT11_COUNT = 11
            if self._ANT_NUM == 12:
                self._ANT12_COUNT = 12
            if self._ANT_NUM == 13:
                self._ANT13_COUNT = 13
            if self._ANT_NUM == 14:
                self._ANT14_COUNT = 14
            if self._ANT_NUM == 15:
                self._ANT15_COUNT = 15
            if self._ANT_NUM == 16:
                self._ANT16_COUNT = 16
            if self._ANT_NUM == 17:
                self._ANT17_COUNT = 17
            if self._ANT_NUM == 18:
                self._ANT18_COUNT = 18
            if self._ANT_NUM == 19:
                self._ANT19_COUNT = 19
            if self._ANT_NUM == 20:
                self._ANT20_COUNT = 20
            if self._ANT_NUM == 21:
                self._ANT21_COUNT = 21
            if self._ANT_NUM == 22:
                self._ANT22_COUNT = 22
            if self._ANT_NUM == 23:
                self._ANT23_COUNT = 23
            if self._ANT_NUM == 24:
                self._ANT24_COUNT = 24


            while copyIndex < len(param):
                if param[copyIndex] == 1:  # RSSI
                    copyIndex += 1
                    self._RSSI = param[copyIndex]
                    copyIndex += 1
                elif param[copyIndex] == 2:  # 标签读取结果
                    copyIndex += 1
                    self._Result = param[copyIndex]
                    if self._Result != 0x00:
                        break
                    copyIndex += 1
                elif param[copyIndex] == 3:  # 标签TID数据
                    copyIndex += 1
                    tid_Len = Helper_Protocol.U16BytesToInt(param, copyIndex)
                    copyIndex += 2
                    b_TID = bytearray(tid_Len)
                    Helper_Protocol.arrayCopy(param, copyIndex, b_TID, 0, len(b_TID))
                    self._TID = Helper_String.PrintHexStringByteSum(b_TID)
                    copyIndex += len(b_TID)
                elif param[copyIndex] == 4:  # 标签用户数据区数据
                    copyIndex += 1
                    userData_Len = Helper_Protocol.U16BytesToInt(param, copyIndex)
                    copyIndex += 2
                    b_UserData = bytearray(userData_Len)
                    Helper_Protocol.arrayCopy(param, copyIndex, b_UserData, 0, len(b_UserData))
                    self._UserData = Helper_String.PrintHexStringByteSum(b_UserData)
                    copyIndex += len(b_UserData)
                    if len(b_UserData) >= 8:
                        self._RFCaliberateTemperatureData = self._UserData[:16]  # RF MODEL403
                elif param[copyIndex] == 5:  # 标签保留区数据
                    copyIndex += 1
                    retain_Len = Helper_Protocol.U16BytesToInt(param, copyIndex)
                    copyIndex += 2
                    b_Retain = bytearray(retain_Len)
                    Helper_Protocol.arrayCopy(param, copyIndex, b_Retain, 0, len(b_Retain))
                    self._RsvdData = Helper_String.PrintHexStringByteSum(b_Retain)
                    copyIndex += len(b_Retain)

                    if len(b_Retain) >= 6:  # RF MODEL403
                        self._RFSensorData = self._RsvdData[0:4]
                        self._RFRSSIData = self._RsvdData[4:8]
                        self._RFTemperatureData = self._RsvdData[8:12]
                elif param[copyIndex] == 6:  # 扩展集线器后，子天线的输出
                    copyIndex += 1
                    antNo = '{:02X}'.format(param[copyIndex])
                    ant = int(antNo, 16)
                    self._Bag = str(ant)
                    copyIndex += 1
                elif param[copyIndex] == 7:  # 标签读取UTC时间戳
                    copyIndex += 1
                    b_UTC = bytearray(8)
                    Helper_Protocol.arrayCopy(param, copyIndex, b_UTC, 0, len(b_UTC))
                    utc1 = Helper_Protocol.GetS32ByBytes(b_UTC, 0)
                    utc2 = Helper_Protocol.GetS32ByBytes(b_UTC, 4) / 1000
                    dateTime = time.localtime(utc1 + utc2)
                    self._ReadTime = time.strftime('%Y-%m-%d %H:%M:%S', dateTime)
                    copyIndex += 8
                elif param[copyIndex] == 8:  # 断点续传标志
                    copyIndex += 1
                    b_SerialNo = bytearray(4)
                    Helper_Protocol.arrayCopy(param, copyIndex, b_SerialNo, 0, len(b_SerialNo))
                    self._SerialNo = b_SerialNo
                    copyIndex += 4
                    self._IsContinue = 1
                elif param[copyIndex] == 9:  #
                    copyIndex += 1
                    b_Frequency = bytearray(4)
                    Helper_Protocol.arrayCopy(param, copyIndex, b_Frequency, 0, len(b_Frequency))
                    self._Frequency = Helper_Protocol.ReverseU32BytesToInt(b_Frequency, 0)
                    copyIndex += 4
                elif param[copyIndex] == 10:  # 标签相位计算方法：(相位值/128)*2π
                    copyIndex += 1
                    self._Phase = param[copyIndex]
                    self._Phase = (self._Phase / 128) * 2 * math.pi  # 标签相位计算方法：(相位值 / 128) * 2
                    copyIndex += 1
                elif param[copyIndex] == 11:  # EM标签 SensorData数据内容
                    copyIndex += 1
                    self._EMSensorData = Helper_String.Bytes2String2(param, copyIndex, 8)
                    copyIndex += 8
                elif param[copyIndex] == 12:  # EPC区数据
                    copyIndex += 1
                    epcData_Len = Helper_Protocol.U16BytesToInt(param,copyIndex)
                    copyIndex += 2
                    b_EpcData = bytearray(epcData_Len)
                    Helper_Protocol.arrayCopy(param, copyIndex, b_EpcData, 0,len(b_EpcData))
                    self._EpcData = Helper_String.PrintHexStringByteSum(b_EpcData)
                    copyIndex += len(b_EpcData)
                elif param[copyIndex] == 13:  #
                    copyIndex += 1
                    g2v2Byte = bytearray(10)
                    Helper_Protocol.arrayCopy(param, copyIndex, g2v2Byte, 0, len(g2v2Byte))
                    self._G2V2Challenge = Helper_String.PrintHexStringByteSum(g2v2Byte)
                    copyIndex += len(g2v2Byte)
                elif param[copyIndex] == 14:  #
                    copyIndex += 1
                    g2v2_Len = Helper_Protocol.U16BytesToInt(param, copyIndex)
                    copyIndex += 2
                    g2v2Byte = bytearray(g2v2_Len)
                    Helper_Protocol.arrayCopy(param, copyIndex, g2v2Byte, 0, len(g2v2Byte))
                    self._G2V2Data = Helper_String.PrintHexStringByteSum(g2v2Byte)
                    copyIndex += len(g2v2Byte)
                elif param[copyIndex] == 15:  # EM标签 SensorData数据内容
                    copyIndex += 1
                    self._CABSensorData = Helper_String.Bytes2String2(param, copyIndex, 4)
                    copyIndex += 4
                elif param[copyIndex] == 16:  # 读取次数
                    copyIndex += 1
                    copyIndex += 4
                elif param[copyIndex] == 17:  # RSSI
                    copyIndex += 1
                    temp = param[copyIndex]
                    self._RSSI_dB = temp - 256 if temp > 127 else temp
                    copyIndex += 1
                elif param[copyIndex] == 18:  # LTU
                    copyIndex += 1
                    self._LTU32SensorData = Helper_String.Bytes2String2(param, copyIndex, 4)
                    copyIndex += 4
                elif param[copyIndex] == 19:  # BrandID
                    copyIndex += 1
                    self._NXPBrandIdentify = Helper_String.Bytes2String2(param, copyIndex, 2)
                    copyIndex += 2
                elif param[copyIndex] == 20:  # EASAlarm
                    copyIndex += 1
                    self._EASFlag = param[copyIndex] & 0xff
                    copyIndex += 1
                else:
                    break

        except Exception as e:
            print("失败，错误信息%s" % e)

    def Init6B(self, data):
        pass

    def InitGB(self, data):
        pass

    #临时算法计算RSSI
    def RSSI(self):
        result = 0
        if self._RSSI_dB != 0:
            result = self._RSSI_dB
        else:

            mantissa = self._RSSI & 0x7
            exponent = (self._RSSI >> 3) & 0x1f
            mantissa_size = 3
            exp = math.pow(2, exponent) * (1 + mantissa / math.pow(2, mantissa_size))
            result = 20 * math.log10(exp)
            result -= 105


        result = round(result * 10) / 10

        return result
