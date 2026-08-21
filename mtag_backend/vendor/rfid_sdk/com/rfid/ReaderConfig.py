import time

from com.rfid import RFIDReader,Param_Option
from com.rfid.RFID_Option import RFID_Option
from com.rfid.enumeration.EAntennaNo import EAntennaNo
from com.rfid.enumeration.EBaudrate import EBaudrate
from com.rfid.enumeration.EGPIUpload import EGPIUpload
from com.rfid.enumeration.ERF_Range import ERF_Range
from com.rfid.helper.Helper_String import Helper_String


class ReaderConfig:

    def Stop(self,ConnID):
        rt = -1
        rtStr = RFID_Option.StopReader(ConnID)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    #   配置网口参数
    #   @param ConnID 连接参数
    #   @param iP	IP地址
    #   @param mask  子网掩码
    #   @param gateway 网关
    #   @param dns DNS
    def SetReaderNetworkPortParam(self,ConnID, iP, mask, gateway, dns):
        rt = -1
        if (not Helper_String.IsNullOrEmpty(iP)) and (not Helper_String.IsNullOrEmpty(mask)) and (not Helper_String.IsNullOrEmpty(gateway)):
            param = iP + "|" + mask + "|" + gateway + "|"
            if not Helper_String.IsNullOrEmpty(dns):
                param += "1," + dns + "&"
            rtStr = Param_Option.Param_Option.SetReaderNetworkPortParam(ConnID, param)
            rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetReaderNetworkPortParam(self,ConnID):
        return Param_Option.Param_Option.GetReaderNetworkPortParam(ConnID)

    def SetReaderGPOState(self,ConnID, dicState):
        rt = -1
        param = ""
        for key in dicState.keys():
            param += key + "," + dicState[key]
            param += "&"
        param = param.rstrip('&')
        rtStr = Param_Option.Param_Option.SetReaderGPOState(ConnID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def SetReaderRestoreFactory(self,ConnID):
        rtStr = Param_Option.Param_Option.SetReaderRestoreFactory(ConnID, "5AA5A55A")
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def SetEPCBasebandParam(self,ConnID,basebandMode,qValue,sesstion,searchType):
        rt = -1
        param = ""
        if basebandMode != None:
            param += "1," + str(basebandMode) + "&"
        if qValue != None:
            param += "2," + str(qValue) + "&"
        if sesstion != None:
            param += "3," + str(sesstion) + "&"
        if searchType != None:
            param += "4," + str(searchType) + "&"

        if param.endswith("&"):
            param = param[0: len(param) - 1]
        rtStr = RFID_Option.SetEPCBasebandParam(ConnID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetEPCBasebandParam(self,ConnID):
        return RFID_Option.GetEPCBasebandParam(ConnID)

    def SetANTPowerParam(self,ConnID,dicPower):
        rt = -1
        param = ""
        for key in dicPower.keys():
            param += str(key) + "," + str(dicPower[key])
            param += "&"
        param = param.rstrip('&')
        rtStr = RFID_Option.SetReaderPower(ConnID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetANTPowerParam(self,ConnID):
        dicPower = {}
        rtStr = RFID_Option.GetANTPowerParam(ConnID)
        result = rtStr.rstrip("&").split("&")
        if len(result) > 0:
            for item in result:
                antPower = item.rstrip(",").split(",")
                if len(antPower) == 2:
                    dicPower[int(antPower[0])] = int(antPower[1])
        return dicPower

    def GetANTPowerParam2(self,ConnID):
        return RFID_Option.GetANTPowerParam(ConnID)

    def SetTagUpdateParam(self,ConnID, repeatTimeFilter, RSSIFilter,dbmFilter):
        if dbmFilter:
            param = "1," + str(repeatTimeFilter) + "&2," + str(RSSIFilter) + "&3," + str(dbmFilter)
        else:
            param = "1," + str(repeatTimeFilter) + "&2," + str(RSSIFilter)
        rtStr = RFID_Option.SetTagUpdateParam(ConnID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetTagUpdateParam(self,ConnID):
        return RFID_Option.GetTagUpdateParam(ConnID)

    def SetReaderUTC(self,ConnID, param):
        ts = self.getTimestamp(param.replace('&', ' ')) * 1000
        tmp = str(ts)
        utc = tmp[0: len(tmp) - 3] + "." + tmp[len(tmp) - 3:] + "0"

        strs = Param_Option.Param_Option.SetReaderUTC(ConnID, utc)
        rt = RFIDReader.RFIDReader.GetReturnData(strs)
        return rt

    def getTimestamp(self,sTime):
        strs = sTime.replace(' ', ':').replace('-', ':').replace('.', ':').rstrip(":").split(":")
        timeArray = None
        if len(strs) == 6:
            Time = strs[0] + "-" + strs[1] + "-" + strs[2] + " " + strs[3] + ":" + strs[4] + ":" + strs[5]
            timeArray = time.strptime(Time, "%Y-%m-%d %H:%M:%S")
        if len(strs) == 7:
            Time = strs[0] + "-" + strs[1] + "-" + strs[2] + " " + strs[3] + ":" + strs[4] + ":" + strs[5] + "." + strs[6]
            timeArray = time.strptime(Time, "%Y-%m-%d %H:%M:%S")
        return int(time.mktime(timeArray))

    def GetReaderUTC(self,ConnID):
        rtStr = Param_Option.Param_Option.GetReaderUTC(ConnID)
        rt = rtStr.rstrip(".").split(".")
        if len(rt) == 2:
            utc1 = int(rt[0])
            utc2 = int(rt[1])
            utc = utc1*1000 + utc2
            time_local = time.localtime(utc / 1000)
            dt = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
            return dt
        else:
            return rtStr

    def SetReaderSerialPortParam(self,connID,baudRate):
        rt = -1
        if baudRate.value >= 0 and baudRate.value <= 5:
            rtStr = str(Param_Option.Param_Option.SetReaderSerialPortParam(connID, baudRate.value))
            rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetReaderSerialPortParam(self,connID):
        baudRateIndex = int(Param_Option.Param_Option.GetReaderSerialPortParam(connID))
        return EBaudrate(baudRateIndex)

    def SetReaderMacParam(self,connID,param):
        rt = -1
        rtStr = Param_Option.Param_Option.SetReaderMacParam(connID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetReaderMacParam(self,connID):
        return Param_Option.Param_Option.GetReaderMacParam(connID).upper()

    def SetReader485(self,connID, param):
        rt = -1
        rtStr = Param_Option.Param_Option.SetReader485(connID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetReader485(self,connID):
        return Param_Option.Param_Option.GetReader485(connID).rstrip("|").split("|")[0]

    def SetReaderServerOrClient(self,connID,workMode,ip,port):
        if workMode.value == 0:
            param = "0|1," + port.strip()
        else:
            if Helper_String.IsIP(ip.strip()) :
                param = "1|2," + ip.strip() + "& 3," + port.strip()
            else:
                param = "1|162," + ip.strip() + "& 3," + port.strip()
        rtStr = Param_Option.Param_Option.SetReaderServerOrClient(connID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetReaderServerOrClient(self,connID):
        result = Param_Option.Param_Option.GetReaderServerOrClient(connID).rstrip("|").split("|")
        if len(result) == 4:
            if result[0] == "0":
                return "Server|" + str(result[1])
            else:
                return "Client|" + str(result[2]) + "|" + str(result[3])
        else:
            return "Error"

    def GetReaderInformation(self,connID):
        return Param_Option.Param_Option.GetReaderInformation(connID)

    def GetReaderBasebandSoftVersion(self,connID):
        return Param_Option.Param_Option.GetReaderBasebandSoftVersion(connID)

    def GetReaderBasebandSerialNo(self,connID):
        return Param_Option.Param_Option.GetReaderBasebandSerialNo(connID)

    def GetReaderProperty(self,connID):
        return RFID_Option.GetReaderProperty(connID)

    def SetReaderRF(self,connID,RF_range):
        rt = -1
        rtStr = RFID_Option.SetReaderRF(connID, RF_range.value)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    #   老版本的频率频段
    DIC_RF = {}
    @staticmethod
    def getDicRf():
        return ReaderConfig.DIC_RF

    @staticmethod
    def InitDIC_RF():
        ReaderConfig.DIC_RFAddItem(0, 920.625, 924.375, 0.25)
        ReaderConfig.DIC_RFAddItem(1, 840.625, 844.375, 0.25)
        ReaderConfig.DIC_RFAddItem(2, 840.625, 844.375, 0.25)
        ReaderConfig.DIC_RFAddItem(2, 920.625, 924.375, 0.25)
        ReaderConfig.DIC_RFAddItem(3, 902.75, 927.25, 0.5)
        ReaderConfig.DIC_RFAddItem(4, 865.7, 868.0, 0.6)
        ReaderConfig.DIC_RFAddItem(5, 916.8, 920.4, 1.2)
        ReaderConfig.DIC_RFAddItem(5, 920.6, 920.8, 0.2)
        ReaderConfig.DIC_RFAddItem(6, 922.25, 927.75, 0.25)
        ReaderConfig.DIC_RFAddItem(7, 923.125, 925.125, 0.25) # 不一定是0.25，步长以后是要改的
        ReaderConfig.DIC_RFAddItem(8, 866.6, 867.4, 0.2)
        ReaderConfig.DIC_RFAddItem(9, 920.125, 925.0, 0.25) # GBT国标测试频段
        ReaderConfig.DIC_RFAddItem(10, 917.3, 920.3, 0.6) # 新增韩国频段
        ReaderConfig.DIC_RFAddItem(11, 902.75, 907.25, 0.5) # 新增巴西频段 2.27 2019 - 6 - 27
        ReaderConfig.DIC_RFAddItem(11, 915.25, 927.25, 0.5) # 新增巴西频段
        ReaderConfig.DIC_RFAddItem(12, 919.25, 922.75, 0.5) # 新增马来西亚频段 2.28 2019 - 7 - 17
        ReaderConfig.DIC_RFAddItem(13, 920.75, 923.25, 0.5) # 新增马来斯里兰卡2.28 2019 - 12 - 31
        ReaderConfig.DIC_RFAddItem(14, 902.75, 914.75, 0.5) # FCC2
        ReaderConfig.DIC_RFAddItem(15, 915.25, 927.25, 0.5) # FCC2
        ReaderConfig.DIC_RFAddItem(16, 915.50, 916.70, 0.4) # ETSI2
        ReaderConfig.DIC_RFAddItem(17, 920.25, 924.75, 0.5) # AUS
        ReaderConfig.DIC_RFAddItem(18, 920.25, 922.75, 0.5) # VIE
        ReaderConfig.DIC_RFAddItem(19, 916.25, 916.25, 0.5) # ISR、
        ReaderConfig.DIC_RFAddItem(20, 915.4, 919, 0.2)  # ZAF
        # DIC_RFAddItem(255, 902.75f, 927.25f, 0.5f);		# CUSTOM

    @staticmethod
    def DIC_RFAddItem(index, fStart, fEnd, jump):
        listItem = []
        while fStart <= fEnd:
            listItem.append(str(fStart))
            fStart += jump
        if index in ReaderConfig.DIC_RF:
            ReaderConfig.DIC_RF[index] = listItem
        else:
            ReaderConfig.DIC_RF[index] = []
            for item in listItem:
                ReaderConfig.DIC_RF[index].append(item)

    def GetReaderRF(self,connID):
        Result = int(RFID_Option.GetReaderRF(connID))
        return ERF_Range(Result)

    def SetReaderAutoSleepParam(self,connID,Switch,time):
        if Switch:
            param = "1|1," + str(time)
        else:
            param = "0"
        rtStr = RFID_Option.SetReaderAutoSleepParam(connID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetReaderAutoSleepParam(self,connID):
        Result = RFID_Option.GetReaderAutoSleepParam(connID).rstrip("|").split("|")
        if Result[0] =="0":
            return "Close"
        elif Result[0] == "1":
            return "Open|" + Result[1]
        else:
            return "Error"

    def GetDataOutputFormat(self,connID):
        rt = ""
        try:
            rt = Param_Option.Param_Option.GetDataOutputFormat(connID)
            if rt.startswith("-"):
                rt = "-1"
        except Exception as e:
            rt = "-1"
        return rt

    def SetReaderANT(self,connID,antNum):
        rt = -1
        rtStr = RFID_Option.SetReaderANT(connID, self.ConvertToNewParam(str(antNum)))
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def ConvertToNewParam(self,oldParam):
        newParam = ""
        antNum = 0
        antNum = int(oldParam)
        if antNum > 255:
            if antNum >= EAntennaNo._24.value:
                antNum -= EAntennaNo._24.value
            if antNum >= EAntennaNo._23.value and antNum < EAntennaNo._24.value:
                antNum -= EAntennaNo._23.value
            if antNum >= EAntennaNo._22.value and antNum < EAntennaNo._23.value:
                antNum -= EAntennaNo._22.value
            if antNum >= EAntennaNo._21.value and antNum < EAntennaNo._22.value:
                antNum -= EAntennaNo._21.value
            if antNum >= EAntennaNo._20.value and antNum < EAntennaNo._21.value:
                antNum -= EAntennaNo._20.value
            if antNum >= EAntennaNo._19.value and antNum < EAntennaNo._20.value:
                antNum -= EAntennaNo._19.value
            if antNum >= EAntennaNo._18.value and antNum < EAntennaNo._19.value:
                antNum -= EAntennaNo._18.value
            if antNum >= EAntennaNo._17.value and antNum < EAntennaNo._18.value:
                antNum -= EAntennaNo._17.value
            if antNum >= EAntennaNo._16.value and antNum < EAntennaNo._17.value:
                antNum -= EAntennaNo._16.value
            if antNum >= EAntennaNo._15.value and antNum < EAntennaNo._16.value:
                antNum -= EAntennaNo._15.value
            if antNum >= EAntennaNo._14.value and antNum < EAntennaNo._15.value:
                antNum -= EAntennaNo._14.value
            if antNum >= EAntennaNo._13.value and antNum < EAntennaNo._14.value:
                antNum -= EAntennaNo._13.value
            if antNum >= EAntennaNo._12.value and antNum < EAntennaNo._13.value:
                antNum -= EAntennaNo._12.value
            if antNum >= EAntennaNo._11.value and antNum < EAntennaNo._12.value:
                antNum -= EAntennaNo._11.value
            if antNum >= EAntennaNo._10.value and antNum < EAntennaNo._11.value:
                antNum -= EAntennaNo._10.value
            if antNum >= EAntennaNo._9.value and antNum < EAntennaNo._10.value:
                antNum -= EAntennaNo._9.value
            newParam += antNum + "|"
            exAntNum = (int(oldParam) - antNum) / 256
            newParam = newParam.rstrip('|')
            newParam += "|25," + ("{:02x}".format(exAntNum)).rjust( 4, '0')
            return newParam
        else:
            return oldParam # + "|25,0000";

    def GetReaderANT(self,connID):
        AntNum = 0
        rtStr = RFID_Option.GetReaderANT(connID)
        param = rtStr.rstrip("|").split("|")
        if len(param) > 1:
            AntNum += int(param[0])
            str = param[1].rstrip("&").split("&")
            for item in str:
                aaa = item.rstrip(",").split(",")
                if aaa[0] == "25":
                    AntNum += int(aaa[1], 16) * 256
                else:
                    AntNum = int(param[0])
        return AntNum

    def GetReaderANT2(self,connID):
        EnableANT = ""
        antNum = 0
        rtStr = RFID_Option.GetReaderANT(connID)
        param = rtStr.rstrip("|").split("|")
        if len(param) > 1:
            antNum += int(param[0])
            str = param[1].rstrip("&").split("&")
            for item in str:
                aaa = item.rstrip(",").split(",")
                if aaa[0] == "25":
                    antNum += int(aaa[1],16) *256
        else:
            antNum = int(param[0])
        if antNum >= EAntennaNo._24.value:
            EnableANT = "24," + EnableANT
            antNum -= EAntennaNo._24.value
        if antNum >= EAntennaNo._23.value and antNum < EAntennaNo._24.value:
            EnableANT = "23," + EnableANT
            antNum -= EAntennaNo._23.value
        if antNum >= EAntennaNo._22.value and antNum < EAntennaNo._23.value:
            EnableANT = "22," + EnableANT
            antNum -= EAntennaNo._22.value
        if antNum >= EAntennaNo._21.value and antNum < EAntennaNo._22.value:
            EnableANT = "21," + EnableANT
            antNum -= EAntennaNo._21.value
        if antNum >= EAntennaNo._20.value and antNum < EAntennaNo._21.value:
            EnableANT = "20," + EnableANT
            antNum -= EAntennaNo._20.value
        if antNum >= EAntennaNo._19.value and antNum < EAntennaNo._20.value:
            EnableANT = "19," + EnableANT
            antNum -= EAntennaNo._19.value
        if antNum >= EAntennaNo._18.value and antNum < EAntennaNo._19.value:
            EnableANT = "18," + EnableANT
            antNum -= EAntennaNo._18.value
        if antNum >= EAntennaNo._17.value and antNum < EAntennaNo._18.value:
            EnableANT = "17," + EnableANT
            antNum -= EAntennaNo._17.value
        if antNum >= EAntennaNo._16.value and antNum < EAntennaNo._17.value:
            EnableANT = "16," + EnableANT
            antNum -= EAntennaNo._16.value
        if antNum >= EAntennaNo._15.value and antNum < EAntennaNo._16.value:
            EnableANT = "15," + EnableANT
            antNum -= EAntennaNo._15.value
        if antNum >= EAntennaNo._14.value and antNum < EAntennaNo._15.value:
            EnableANT = "14," + EnableANT
            antNum -= EAntennaNo._14.value
        if antNum >= EAntennaNo._13.value and antNum < EAntennaNo._14.value:
            EnableANT = "13," + EnableANT
            antNum -= EAntennaNo._13.value
        if antNum >= EAntennaNo._12.value and antNum < EAntennaNo._13.value:
            EnableANT = "12," + EnableANT
            antNum -= EAntennaNo._12.value
        if antNum >= EAntennaNo._11.value and antNum < EAntennaNo._12.value:
            EnableANT = "11," + EnableANT
            antNum -= EAntennaNo._11.value
        if antNum >= EAntennaNo._10.value and antNum < EAntennaNo._11.value:
            EnableANT = "10," + EnableANT
            antNum -= EAntennaNo._10.value
        if antNum >= EAntennaNo._9.value and antNum < EAntennaNo._10.value:
            EnableANT = "9," + EnableANT
            antNum -= EAntennaNo._9.value
        if antNum >= EAntennaNo._8.value and antNum < EAntennaNo._9.value:
            EnableANT = "8," + EnableANT
            antNum -= EAntennaNo._8.value
        if antNum >= EAntennaNo._7.value and antNum < EAntennaNo._8.value:
            EnableANT = "7," + EnableANT
            antNum -= EAntennaNo._7.value
        if antNum >= EAntennaNo._6.value and antNum < EAntennaNo._7.value:
            EnableANT = "6," + EnableANT
            antNum -= EAntennaNo._6.value
        if antNum >= EAntennaNo._5.value and antNum < EAntennaNo._6.value:
            EnableANT = "5," + EnableANT
            antNum -= EAntennaNo._5.value
        if antNum >= EAntennaNo._4.value and antNum < EAntennaNo._5.value:
            EnableANT = "4," + EnableANT
            antNum -= EAntennaNo._4.value
        if antNum >= EAntennaNo._3.value and antNum < EAntennaNo._4.value:
            EnableANT = "3," + EnableANT
            antNum -= EAntennaNo._3.value
        if antNum >= EAntennaNo._2.value and antNum < EAntennaNo._3.value:
            EnableANT = "2," + EnableANT
            antNum -= EAntennaNo._2.value
        if antNum >= EAntennaNo._1.value and antNum < EAntennaNo._2.value:
            EnableANT = "1," + EnableANT
        return EnableANT.rstrip(',')

    def SetReaderWG(self,connID,wiegandSwitch,wiegandFormat,wiegandDetails, OutputAddress):
        rt = -1
        param = str(wiegandSwitch) + "|" + str(wiegandFormat) + "|" + str(wiegandDetails)
        if OutputAddress != None:
            param = "|,1" + OutputAddress
        rtStr = Param_Option.Param_Option.SetReaderWG(connID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetReaderWG(self,connID):
        Result = Param_Option.Param_Option.GetReaderWG(connID).rstrip("|").split("|")
        if len(Result) == 3:
            param = ""
            if Result[0] == "0":
                param += "Close|"
            elif Result[0] == "1":
                param += "Open|"
            else:
                param += "Error|"

            if Result[1] == "0":
                param += "Wiegand26|"
            elif Result[1] == "1":
                param += "Wiegand34|"
            elif Result[1] == "2":
                param += "Wiegand66|"
            else:
                param += "Error|"

            if Result[2] == "0":
                param += "end_of_the_EPC_data"
            elif Result[2] == "1":
                param += "end_of_the_TID_data"
            else:
                param += "Error"
        else:
            return "Error"

    def GetReaderGPIState(self,connID):
        Result = Param_Option.Param_Option.GetReaderGPIState(connID).rstrip("&").split("&")
        temp = ""
        for str in Result:
            if len(str.rstrip(",").split(",")) == 2:
                if str.rstrip(",").split(",")[1] == "0":
                    temp += str.rstrip(",").split(",")[0] + ",Low&"
                elif str.rstrip(",").split(",")[1] == "1":
                    temp += str.rstrip(",").split(",")[0] + ",High&"
                else:
                    return "Error"
        return temp.rstrip('&')

    def SetReaderGPIParam(self,connID, GPINum,triggerStart,triggerCode,triggeerStop,DelayTime , isUpload,customCMD):
        rt = -1
        param = ""
        param = str(GPINum.value) + "|" + str(triggerStart.value) + "|"
        CodeNum = triggerCode.value
        if CodeNum == 0:
            param += "021000020101|"
        elif CodeNum == 1:
            param += "021000050101020006|"
        elif CodeNum == 2:
            param += "021000020301|"
        elif CodeNum == 3:
            param += "021000050301020006|"
        elif CodeNum == 4:
            param += "021000020F01|"
        elif CodeNum == 5:
            param += "021000050F01020006|"
        elif CodeNum == 6:
            param += "02100002FF010|"
        elif CodeNum == 7:
            param += "02100005FF01020006|"
        elif CodeNum == 8:
            param += "02100005FF010A000F|"
        elif CodeNum == 9:
            param += "02100008FF010200060A000F|"
        elif CodeNum == 10:
            param += "02100005FF010AFFFF|"
        elif CodeNum == 11:
            param += "02100008FF010200060AFFFF|"
        else:
            param += customCMD + "|"

        param += str(triggeerStop.value) + "|"
        if triggeerStop.value == 6:
            param += "1," + DelayTime


        if isUpload == EGPIUpload.Upload_Start_Trigger_Msg:
            param += "2,0"
        elif isUpload == EGPIUpload.Upload_Trigger_Msg:
            param += "2,1"
        elif isUpload == EGPIUpload.No_Upload_Trigger_Msg:
            param += "2,2"
        elif isUpload == EGPIUpload.No_Upload_Trigger_Msg_Resp:
            param += "2,3"

        rtStr = Param_Option.Param_Option.SetReaderGPIParam(connID, param.rstrip('|'))
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetReaderGPIParam(self,connID, GPINum):
        Result = Param_Option.Param_Option.GetReaderGPIParam(connID, str(GPINum)).rstrip("|").split("|")
        if len(Result) == 5:
            str = ""
            if Result[0] == "0":
                str += "OFF|"
            elif Result[0] == "1":
                str += "Low level|"
            elif Result[0] == "2":
                str += "High level|"
            elif Result[0] == "3":
                str += "Rising edge|"
            elif Result[0] == "4":
                str += "Falling edge|"
            elif Result[0] == "5":
                str += "Any edge|"
            else:
                str += "Error|"

            if Result[1] == "021000020101":
                str += "Single Antenna read EPC|"
            elif Result[1] == "021000050101020006":
                str += "Single Antenna read EPC and TID|"
            elif Result[1] == "021000020301":
                str += "Double Antenna read EPC|"
            elif Result[1] == "021000050301020006":
                str += "Double Antenna read EPC and TID|"
            elif Result[1] == "021000020701":
                str += "Four Antenna read EPC|"
            elif Result[1] == "021000050F01020006":
                str += "Four Antenna read EPC and TID|"
            elif Result[1] == "02100002FF010":
                str += "Eight Antenna read EPC|"
            elif Result[1] == "02100005FF01020006":
                str += "Eight Antenna read EPC and TID|"
            elif Result[1] == "02100005FF010A000F":
                str += "12 Antenna read EPC|"
            elif Result[1] == "02100008FF010200060A000F":
                str += "12 Antenna read EPC and TID|"
            elif Result[1] == "02100005FF010AFFFF":
                str += "24 Antenna read EPC|"
            elif Result[1] == "02100008FF010200060AFFFF":
                str += "24 Antenna read EPC and TID|"
            else:
                str += "Custom Read|"

            if Result[2] == "0":
                str += "OFF|"
            elif Result[2] == "1":
                str += "Low level|"
            elif Result[2] == "2":
                str += "High level|"
            elif Result[2] == "3":
                str += "Rising edge|"
            elif Result[2] == "4":
                str += "Falling edge|"
            elif Result[2] == "5":
                str += "Any edge|"
            elif Result[2] == "6":
                str += "Delay|"
            else:
                str += "Error|"

            str += Result[3] + "|"
            if Result[4] == "0":
                str += "ON"
            if Result[4] == "1":
                str += "OFF"
            return str

        elif len(Result) == 4:
            str = ""
            if Result[0] == "0":
                str += "OFF|"
            elif Result[0] == "1":
                str += "Low level|"
            elif Result[0] == "2":
                str += "High level|"
            elif Result[0] == "3":
                str += "Rising edge|"
            elif Result[0] == "4":
                str += "Falling edge|"
            elif Result[0] == "5":
                str += "Any edge|"
            else:
                str += "Error|"

            if Result[1] == "021000020101":
                str += "Single Antenna read EPC|"
            elif Result[1] == "021000050101020006":
                str += "Single Antenna read EPC and TID|"
            elif Result[1] == "021000020301":
                str += "Double Antenna read EPC|"
            elif Result[1] == "021000050301020006":
                str += "Double Antenna read EPC and TID|"
            elif Result[1] == "021000020701":
                str += "Four Antenna read EPC|"
            elif Result[1] == "021000050F01020006":
                str += "Four Antenna read EPC and TID|"
            else:
                str += "Error|"

            if Result[2] == "0":
                str += "OFF|"
            elif Result[2] == "1":
                str += "Low level|"
            elif Result[2] == "2":
                str += "High level|"
            elif Result[2] == "3":
                str += "Rising edge|"
            elif Result[2] == "4":
                str += "Falling edge|"
            elif Result[2] == "5":
                str += "Any edge|"
            elif Result[2] == "6":
                str += "Delay|"
            else:
                str += "Error|"
            str += Result[3]
            return str
        else:
            return "Error"

    def SetBreakPointUpload(self,connID,Switch):
        rt = -1
        param = ""
        if Switch:
            param = "1"
        else:
            param = "0"
        rtStr = Param_Option.Param_Option.SetBreakPointUpload(connID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetBreakPointUpload(self,connID):
        Result = Param_Option.Param_Option.GetBreakPointUpload(connID)
        if Result == "1":
            return "Open"
        elif Result == "0":
            return "Close"
        else:
            return "Error"

    def GetBreakPointCacheTag(self,connID):
        Result = Param_Option.Param_Option.GetBreakPointCacheTag(connID)
        if Result == "0":
            return "Success"
        elif Result == "1":
            return "Null"
        elif Result == "2":
            return "Receive Over"
        else:
            return "Error"

    def ClearBreakPointCache(self,connID):
        rt = -1
        rtStr = Param_Option.Param_Option.ClearBreakPointCache(connID).rstrip("|").split("|")[0]
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def SetDHCP(self,connID,param):
        rtStr = ""
        if param:
            rtStr = Param_Option.Param_Option.SetDHCP(connID, "1")
        else:
            rtStr = Param_Option.Param_Option.SetDHCP(connID, "0")
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetDHCP(self,connID):
        if Param_Option.Param_Option.GetDHCP(connID).startswith("1"):
            return True
        else:
            return False
    def SetReaderSelfCheck(self,connID, Switch, ip):
        rt = -1
        rtStr = ""
        param = ""
        if Switch:
            param = "1|" + ip.trim()
        else:
            param = "0"
        rtStr = Param_Option.Param_Option.SetReaderSelfCheck(connID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetReaderSelfCheck(self,connID):
        Result = Param_Option.Param_Option.GetReaderSelfCheck(connID).rstrip("|").split("|")
        if Result[0] == "0":
            return "Close"
        elif Result[0] == "1":
            return "Open|" + Result[1]
        else:
            return "Error"

    # 搜索WIFI热点
    def SearchWIFI(self,ConnID):
        rt = -1
        rtStr = Param_Option.Param_Option.SearchWIFI(ConnID)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    # 请求Wifi搜索结果数据包
    def RequestWiFiInfo(self,ConnID,index):
        rt = ""
        rt = Param_Option.Param_Option.RequestWiFiInfo(ConnID, index)
        return rt

    # 请求Wifi搜索结果，并将其存入txt文件
    def RequestWiFiDataToTxt(self,ConnID,filepath):
        pass

    #   连接WIFI热点
    #   ConnID  连接参数
    #   name    wifi名称
    #   pwd wifi密码
    #   authType    认证类型
    #   encryption  加密算法
    def ConnectWIFI(self,ConnID, name, pwd, authType,encryption):
        if authType == None:
            authType = 0
        if encryption == None:
            encryption = 0
        param = name + "|1," + pwd + "&2," + authType + "&3," + encryption
        if pwd == "":
            param = name
        rtStr = Param_Option.Param_Option.ConnectWIFI(ConnID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    def GetWifiConnectInfo(self,ConnID):
        rt = ""
        rt = Param_Option.Param_Option.GetWifiConnectInfo(ConnID)
        return rt

    # 配置Wifi网卡IP
    def SetReaderWifiIP(self,ConnID, iP, mask, gateway, dns):
        rt = -1
        if Helper_String.IsNullOrEmpty(iP) or Helper_String.IsNullOrEmpty(iP) or Helper_String.IsNullOrEmpty(iP):
            return rt
        param = iP + "|" + mask + "|" + gateway + "|"
        if not Helper_String.IsNullOrEmpty(dns):
            param += "1," + dns + "&"

        param = param.rstrip('&')
        param = param.rstrip('|')
        rtStr = Param_Option.Param_Option.SetReaderWifiIP(ConnID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    # 查询网卡IP
    def GetReaderWifiIP(self,ConnID):
        return Param_Option.Param_Option.GetReaderWifiIP(ConnID)

    # 配置读写器WiFi网卡开关
    def SetWiFiSwitch(self,ConnID, isOpen):
        rt = -1
        param = 0
        if isOpen:
            param = 1
        rtStr = Param_Option.Param_Option.SetWiFiSwitch(ConnID, param)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    # 查询WiFi开关状态
    def GetWiFiSwitchState(self,ConnID):
        rt = -1
        rtStr = Param_Option.Param_Option.GetWiFiSwitchState(ConnID)
        rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        return rt

    #    设置蜂鸣器开关
    #   开关 0：读写器控制,1：上位机控制
    def SetBuzzerSwitch(self,connID, param):
        res = Param_Option.Param_Option.SetBuzzerSwitch(connID, param)
        if res.startswith("0"):
            res = "0|OK"
        return res

    #    查询蜂鸣器开关
    #   开关 0：读写器控制,1：上位机控制
    def GetBuzzerSwitch(self,connID):
        res = Param_Option.Param_Option.GetBuzzerSwitch(connID)
        return res

    #   设置蜂鸣器控制
    #   eg:0001 ==> byte0: 00：蜂鸣器停止/01：响  byte1：00: 蜂鸣器响一次/01:常响
    def SetBuzzerControl(self,connID, param):
        res = Param_Option.Param_Option.SetBuzzerControl(connID, param)
        if res.startswith("0"):
            res = "0|OK"
        return res

    #   查询指示灯
    #   0 或者 0|1,20
    def GetReaderStateLED(self,connID):
        res = Param_Option.Param_Option.GetReaderStateLED(connID)
        return res

    #   配置状态指示灯
    #   connID  连接标识
    #   isOpen  开或者关
    #   time    亮灯时间
    def SetReaderStateLED(self,connID, isOpen,time):
        param = ""
        if isOpen:
            param = "1|1," + time
        else:
            param = "0"
        res = Param_Option.Param_Option.SetReaderStateLED(connID, param)
        if res.__contains__("0"):
            res = "0|OK"
        return res

    #   下发白名单到读写器
    def LoadWhiteList(self,connID, dataIndex,param):
        rt = ""
        try:
            rt = Param_Option.Param_Option.LoadWhiteList(connID, dataIndex, param)
        except Exception as e:
            rt = "-1"
        return rt

    def GetAntennaStandingWaveRatio(self,connID, antNo, FreqId):
        if FreqId == None:
            FreqId = 0
        rt = ""
        try:
            RFID_Option.StopReader(connID)
            if antNo > EAntennaNo._8.value:
                RFID_Option.SendCarrier(connID, "0|" + str(FreqId) + "|1," + ("{:02x}".format(antNo / 256)).rjust(4,'0'))
            else:
                RFID_Option.SendCarrier(connID, str(antNo) + "|" + str(FreqId))
            rt = RFID_Option.Get_0101_05(connID)
            RFID_Option.StopReader(connID)
        except Exception as e:
            rt = "-1"
        return rt

    def ReSetReader(self,connID):
        Param_Option.Param_Option.ReSetReader(connID)

    #   设置白名单动作参数
    def SetWhitelistLabelAction(self,connID,param):
        res = Param_Option.Param_Option.SetWhitelistLabelAction(connID, param)
        if res.__contains__("0"):
            res = "0|OK"
        return res
    #   获取白名单动作参数
    def GetWhitelistLabelAction(self,connID):
        res = Param_Option.Param_Option.GetWhitelistLabelAction(connID)
        if res.startswith("-"):
            res = "-1"
        return res

    #   设置心跳设置
    def SetHeartbeat(self,connID, param):
        res = Param_Option.Param_Option.SetHeartbeat(connID, param)
        if res.__contains__("0"):
            res = "0|OK"
        return res

    #   获取心跳设置
    def GetHeartbeatSetting(self,connID):
        res = Param_Option.Param_Option.GetHeartbeat(connID)
        if res.startswith("-"):
            res = "-1"
        return res

    #   获取读写器电量
    def GetReaderElectricity(self,connID):
        res = Param_Option.Param_Option.GetReaderElectricity(connID)
        if res.startswith("-"):
            res = "-1"
        return res

    #   启动扫描头
    def SetScanHead(self,connID):
        res = Param_Option.Param_Option.SetScanHead(connID)
        if res.startswith("-"):
            res = "-1"
        return res

    #   设置标签数据输出格式
    def SetDataOutputFormat(self, connID, swith, outputFormat, outDataType, startData, endData, dataStartByte, dataLen):
        rt = ""
        try:
            param = ""
            param += swith + "|" + outputFormat + "|" + outDataType + "|"
            param += "000" + str(int(len(startData) / 2)) if len(startData) % 2 == 0 else str(int((len(startData) + 1) / 2))
            param += startData if len(startData) % 2 == 0 else startData.rjust(len(startData) + 1, '0')
            param += "|00|00|" + "000"
            param += str(int(len(endData) / 2)) if len(endData) % 2 == 0 else str(int((len(endData) + 1) / 2))
            param += (endData if len(endData) % 2 == 0 else endData.rjust(len(endData) + 1, '0'))
            if dataStartByte: # 可选参数 数据区域
                rtParam = "|1,"
                rtParam += "{:x}".format(int(dataStartByte)).rjust( 4, '0')
                rtParam += "{:x}".format(int(dataLen)).rjust( 2, '0')
                param += rtParam
            rt = Param_Option.Param_Option.SetDataOutputFormat(connID, param)
        except Exception as e:
            rt = "-1"
        return rt

    #   获取数据输出格式
    def GetDataOutputFormat(self,connID):
        res = Param_Option.Param_Option.GetDataOutputFormat(connID)
        if res.startswith("-"):
            res = "-1"
        return res

    #   获取UDP参数
    def GetUDPParams(self,connID):
        res = Param_Option.Param_Option.GetUDPParams(connID)
        if res.startswith("-"):
            res = "-1"
        return res

    #   设置UDP参数
    def SetUDPParams(self,connID,param):
        temp = param
        strs = temp.rstrip("|").split("|")
        if len(strs) != 2:
            return "Params Error"

        p1 = (hex(int(strs[0]))[2:]).rjust(4,'0')
        param = p1 + "|"
        strs2 = strs[1].rstrip(".").split(".")
        for i in range(0,len(strs2)):
            temp2 = (hex(int(strs2[i]))[2:]).rjust(2,'0')
            param += temp2
        res = Param_Option.Param_Option.SetUDPParams(connID, param)
        if res.startswith("-"):
            res = "-1"
        return res

    #   查询国标时钟同步参数
    def GetGBGardner(self,connID):
        res = Param_Option.Param_Option.GetGBGardner(connID)
        if res.startswith("-"):
            res = "-1"
        return res

    #   获取自定义编码
    def GetCustomCode(self,connID):
        res = Param_Option.Param_Option.GetCustomCode(connID)
        if res.startswith("-"):
            res = "-1"
        return res

    #   设置自定义编码
    def SetCustomCode(self,connID,param):
        res = Param_Option.Param_Option.SetCustomCode(connID,param)
        if res.startswith("-"):
            res = "-1"
        return res

    #   获取读写器温度
    def GetReaderTemperature(self,connID):
        res = Param_Option.Param_Option.GetReaderTemperature(connID)
        if res.startswith("-"):
            res = "-1"
        return res

    #   获取RFID温度
    def GetRFIDTemperature(self, connID):
        try:
            res = RFID_Option.GetRFIDTemperature(connID)
            if res.startswith("-"):
                res = "-1"
        except Exception as e:
                res = "-2"
        return res


    #   配置EPC扩展基带参数
    def SetEPCBaseExpandBandParam(self, connID,param):
        try:
            res = RFID_Option.SetEPCBaseExpandBandParam(connID,param)
            if res.startswith("-"):
                res = "-1"
        except Exception as e:
            res = "-2"
        return res

    #   获取EPC扩展基带参数
    def GetEPCBaseExpandBandParam(self, connID):
        try:
            res = RFID_Option.GetEPCBaseExpandBandParam(connID)
            if res.startswith("-"):
                res = "-1"
        except Exception as e:
            res = "-2"
        return res

    #   获取自定义编码
    def GetSN(self, connID):
        try:
            res = Param_Option.Param_Option.GetReaderBasebandSerialNo(connID)
            if res.startswith("-"):
                res = "-1"
        except Exception as e:
            res = "-2"
        return res

    #   设置NTP
    def SetReaderSelfNTP(self,connID, Switch,ip):
        rt = -1
        try:
            rtStr = ""
            param = ""
            if Switch:
                if Helper_String.IsNullOrEmpty(ip):
                    param = "1"
                else:
                    param = "1|" + ip
            else:
                param = "0"
            rtStr = Param_Option.Param_Option.SetReaderNTP(connID, param)
            rt = RFIDReader.RFIDReader.GetReturnData(rtStr)
        except Exception as e:
            pass
        return rt

    #   查询NTP
    def GetReaderNTP(self,connID):
        Result = Param_Option.Param_Option.GetReaderNTP(connID).rstrip("|").split("|")
        if Result[0] == "0":
            return "Close"
        elif Result[0] == "1":
            return "Open|" + Result[1]
        else:
            return "Error"

    def readerXfer(self,connID,param, timout):
        if timout == None:
            timout = 3000
        res = None
        try:
            rt = Param_Option.Param_Option.readerXfer(connID, Helper_String.Bytes2String(param), timout)
            if not rt.startswith("-"):
                res = Helper_String.hexStringToBytes(rt)
        except Exception as e:
            pass
        return res


