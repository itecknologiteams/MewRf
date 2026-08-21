import math
import time
from time import sleep
from com.rfid.Param_Option import Param_Option
from com.rfid.RFIDReader import RFIDReader
from com.rfid.RFID_Option import RFID_Option
from com.rfid.ReaderConfig import ReaderConfig
from com.rfid.ReaderLanguage import ReaderLanguage
from com.rfid.enumeration.EASTSwitchMode import EASTSwitchMode
from com.rfid.enumeration.EAntennaNo import EAntennaNo
from com.rfid.enumeration.EBasebandRate import EBasebandRate
from com.rfid.enumeration.EBaudrate import EBaudrate
from com.rfid.enumeration.EBuzzerControl import EBuzzerControl
from com.rfid.enumeration.EBuzzerType import EBuzzerType
from com.rfid.enumeration.EGPIO import EGPIO
from com.rfid.enumeration.EGPIState import EGPIState
from com.rfid.enumeration.EGPIUpload import EGPIUpload
from com.rfid.enumeration.ELBTWorkMode import ELBTWorkMode
from com.rfid.enumeration.EOutputFormat import EOutputFormat
from com.rfid.enumeration.EOutputSwitch import EOutputSwitch
from com.rfid.enumeration.ERF_Range import ERF_Range
from com.rfid.enumeration.EReadBank import EReadBank
from com.rfid.enumeration.EReadSpecial import EReadSpecial
from com.rfid.enumeration.EReaderEnum import EReaderEnum
from com.rfid.enumeration.EReaderResult import EReaderResult
from com.rfid.enumeration.ESearchType import ESearchType
from com.rfid.enumeration.ETriggerStart import ETriggerStart
from com.rfid.enumeration.ETriggerStop import ETriggerStop
from com.rfid.enumeration.EWF_Mode import EWF_Mode
from com.rfid.enumeration.EWorkMode import EWorkMode
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.interface.IAsynchronousMessage import IAsynchronousMessage
from com.rfid.interface.ISearchDevice import ISearchDevice
from com.rfid.models.AntennaStandingWave_Model import AntennaStandingWave_Model
from com.rfid.models.EPCExtendedParam_Model import EPCExtendedParam_Model
from com.rfid.models.EpcBaseband_Model import EpcBaseband_Model
from com.rfid.models.ReaderAntPower_Model import ReaderAntPower_Model
from com.rfid.models.ReaderAutoSleep_Model import ReaderAutoSleep_Model
from com.rfid.models.ReaderBoolean_Model import ReaderBoolean_Model
from com.rfid.models.ReaderBuzzer_Model import ReaderBuzzer_Model
from com.rfid.models.ReaderDataOutput_Model import ReaderDataOutput_Model
from com.rfid.models.ReaderGPIParam_Model import ReaderGPIParam_Model
from com.rfid.models.ReaderGPIState_Model import ReaderGPIState_Model
from com.rfid.models.ReaderGPOState_Model import ReaderGPOState_Model
from com.rfid.models.ReaderInfo_Model import ReaderInfo_Model
from com.rfid.models.ReaderLED_Model import ReaderLED_Model
from com.rfid.models.ReaderNetwork_Model import ReaderNetwork_Model
from com.rfid.models.ReaderRF_Model import ReaderRF_Model
from com.rfid.models.ReaderSerial_Model import ReaderSerial_Model
from com.rfid.models.ReaderString_Model import ReaderString_Model
from com.rfid.models.ReaderTagUpdate_Model import ReaderTagUpdate_Model
from com.rfid.models.ReaderTime_Model import ReaderTime_Model
from com.rfid.models.ReaderWorkMode_Model import ReaderWorkMode_Model
from com.rfid.models.ReaderWorkingAntSet_Model import ReaderWorkingAntSet_Model
from com.rfid.models.TagData_Model import TagData_Model
from com.rfid.models.TagFilter_Model import TagFilter_Model
from com.rfid.models.Tag_Model import Tag_Model


class Reader(IAsynchronousMessage,ISearchDevice):

    def __init__(self):
        self.__connID = ""
        self.__readerConfig = ReaderConfig()
        self.__initFlag = False
        #   读写器所用天线
        self.__readerAnt = ReaderWorkingAntSet_Model()
        #   读写器扩展读
        self.__readExtendedAreaList = {}
        #   读写器读特殊区
        self.__readSpecialHashSet = []
        #   读写器过滤
        self.__tagFilterList = {}
        #   读取数据集合(现用)
        self.__tagModelList = []
        #   断点续传 数量计算
        self.__cacheCount = 0
        #   回调hash分发
        self.__IAsynchHash = {}
        #   回调hash分发ISearchDevice接口
        self.__ISearchHash = {}
        #   TCP服务监听到的多设备
        self.__readerList = {}
        # 监听时所用的监听连接ID
        self.__listenConnID = "Listener"

    def getConnID(self):
        return self.__connID

    #   读写器初始化方式（true为异步方式，false为同步方式）
    def getInitFlag(self):
        return self.__initFlag

    #   给同步连接方式，获取tag标签数据
    def GetReaderList(self):
        readers = []
        for item in self.__readerList:
            readers.append(item)
        return readers

    #   同步方式初始化连接
    #   * @param param 连接方式+连接参数,例(TCP:192.168.1.116:9090)
    def initReader(self,param,log = None):
        if log == None:
            self.__initFlag = False
        else:
            self.__initFlag = True
        return self.connectReader(param, log)

    #       读写器配置查询
    #      *
    #      * @param key 查询项
    #      * @param val 参数值，作为返回参数
    #      * @return ReaderResult返回枚举
    def paramGet(self,key,val):
        #   没有connID
        if Helper_String.IsNullOrEmpty(self.__connID):
            return EReaderResult.RT_NOT_CONNECT_ERR
        result = ""
        readerStringModel = None
        try:
            # region
            if key == EReaderEnum.RO_ReaderInformation:
                readerInfoModel = val
                # 查询
                # 下面这两个，部分机型没有。如果异常错误，需捕获，设置为空
                try:
                    # 读写器信息
                    result = Param_Option.GetReaderInformation(self.__connID)
                    readerInfoModel.softVersion = result.rstrip("|").split("|")[0]
                    readerInfoModel.name = result.rstrip("|").split("|")[1]
                    readerInfoModel.powerTime = int(result.rstrip("|").split("|")[2])
                except:
                    readerInfoModel.softVersion = ""
                    readerInfoModel.name = ""
                    readerInfoModel.powerTime = ""
                try:
                    # 基带版本
                    result = Param_Option.GetReaderBasebandSoftVersion(self.__connID)
                    readerInfoModel.basebandVersion = result
                except:
                    readerInfoModel.basebandVersion = ""

                # 读写器SN
                result = self.__readerConfig.GetSN(self.__connID)
                readerInfoModel.readerSN = result
                # 读写器能力查询
                result = RFIDReader._Config.GetReaderProperty(self.__connID)
                minPower = result.rstrip("|").split("|")[0]
                maxPower = result.rstrip("|").split("|")[1]
                antCount = result.rstrip("|").split("|")[2]
                readerInfoModel.minPower = int(minPower)
                readerInfoModel.maxPower = int(maxPower)
                readerInfoModel.antCount = int(antCount)
                # 支持的频段
                try:
                    RFList = readerInfoModel.RFList
                    RFList.clear()
                    for  item in result.rstrip("|").split("|")[3].rstrip(",").split(","):
                        RFList.append(ERF_Range(int(item)))
                except:
                    pass
                # 支持的协议
                try:
                    protocolList = readerInfoModel.protocolList
                    protocolList.clear()
                    for item in result.rstrip("|").split("|")[4].rstrip(",").split(","):
                        protocolList.append(int(item))
                except:
                    pass
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RO_ReaderAntennaStandingWaveRatio:
                #   查询驻波比
                antennaStandingWaveModel = val
                if antennaStandingWaveModel.antNum == None:
                    return EReaderResult.RT_INVALID_PARA_ERR
                antNum = antennaStandingWaveModel.antNum.value
                result = self.__readerConfig.GetAntennaStandingWaveRatio(self.__connID, antNum,None)
                if result.startswith("-"):
                    return EReaderResult.RT_FAILED_ERR
                array_rt = result.rstrip("|").split("|")
                # V = 前项 - 后项 （单位）10毫伏
                v = int(array_rt[0]) - int(array_rt[1])
                if v < 5:
                    return EReaderResult.RT_NOT_CONNECT_INFINITY_ERR
                RL = v * 10.0 / 44
                S11 = math.pow(10, RL / -20)
                SWR = (1 + S11) / (1 - S11)
                srl = round(RL, 2)
                sswr = round(SWR, 2)
                antennaStandingWaveModel.forwardPower = int(array_rt[0])
                antennaStandingWaveModel.backwardPower = int(array_rt[1])
                antennaStandingWaveModel.returnLoss = str(srl)
                antennaStandingWaveModel.standingWaveRatio = str(sswr) + ":1"
                return EReaderResult.RT_OK

            elif key == EReaderEnum.RO_ReaderTemperature:
                #   查询读写器温度
                readerStringModel = val
                result = self.__readerConfig.GetRFIDTemperature(self.__connID)
                readerStringModel.data = result
                return EReaderResult.RT_OK
            if key == EReaderEnum.RO_ReaderGPIState:
                #   查询GPI状态
                readerGPIStateModel = val
                dicState = readerGPIStateModel.dicState
                dicState.clear()
                strState = Param_Option.GetReaderGPIState(self.__connID).rstrip("&").split("&")
                for item in strState:
                    aaa = item.rstrip(",").split(",")
                    dicState[EGPIO(int(aaa[0])-1)] = EGPIState(int(aaa[1]))
                return EReaderResult.RT_OK
            #endregion
            #region Reader配置
            elif key == EReaderEnum.RW_ReaderSerialPortParam:
                #   查询串口参数
                readerSerialModel = val
                baudrate = self.__readerConfig.GetReaderSerialPortParam(self.__connID)
                readerSerialModel.baudrate = baudrate
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_Reader485Param:
                #   查询485参数
                readerSerialModel1 = val
                result = Param_Option.GetReader485(self.__connID)
                readerSerialModel1.address = int(result.rstrip("|").split("|")[0])
                baudrateNum = int(result.rstrip("|").split("|")[1])
                readerSerialModel1.baudrate = EBaudrate(baudrateNum)
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_ReaderNetwork:
                readerNetWorkModel = val
                # 查DCHP
                dhcpSwitch = False
                if Param_Option.GetDHCP(self.__connID).startswith("1"):
                    dhcpSwitch = True
                readerNetWorkModel.DhcpSwitch = dhcpSwitch
                # 查Mac地址
                mac = self.__readerConfig.GetReaderMacParam(self.__connID)
                readerNetWorkModel.Mac = mac
                # 查IPV4和IPV6
                result = self.__readerConfig.GetReaderNetworkPortParam(self.__connID)
                readerNetWorkModel.getReaderNetWork(result)
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_ReaderTime:
                # 查读写器时间
                readerTimeModel = val
                # 获取UTC
                readerTime = Param_Option.GetReaderUTC(self.__connID)
                if readerTime:
                    tre_timeArray = time.localtime(float(readerTime))
                    tre_otherStyleTime = time.strftime("%Y-%m-%d %H:%M:%S", tre_timeArray)
                    readerTimeModel.UTC = tre_otherStyleTime
                # 获取NTP
                result = Param_Option.GetReaderNTP(self.__connID)
                if result.startswith("1"):
                    readerTimeModel.NTP_Switch = True
                    readerTimeModel.IP = result.split("|")[1]
                else:
                    readerTimeModel.NTP_Switch = False
                    readerTimeModel.IP = ""
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_ReaderWorkMode:
                #   查工作模式
                readerWorkModeModel = val
                result = self.__readerConfig.GetReaderServerOrClient(self.__connID)
                if result.startswith("Error"):
                    return EReaderResult.RT_FAILED_ERR
                elif result.startswith("Server"):
                    readerWorkModeModel.workMode = EWorkMode.Server
                    readerWorkModeModel.port = int(result.rstrip("|").split("|")[1])
                elif result.startswith("Client"):
                    readerWorkModeModel.workMode = EWorkMode.Client
                    readerWorkModeModel.ip = result.rstrip("|").split("|")[1]
                    readerWorkModeModel.port = int(result.rstrip("|").split("|")[2])
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_ReaderBreakPointUpload:
                #   查断点续传
                readerBooleanModel = val
                result = Param_Option.GetBreakPointUpload(self.__connID)
                if result.startswith("1"):
                    readerBooleanModel.flag = True
                else:
                    readerBooleanModel.flag = False
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_ReaderBuzzerSwitch:
                #   查蜂鸣器
                readerBuzzerModel = val
                result = Param_Option.GetBuzzerSwitch(self.__connID)
                if result == "1":
                    readerBuzzerModel.buzzerControl = EBuzzerControl.PCControl
                    return EReaderResult.RT_OK
                elif  result == "0":
                    readerBuzzerModel.buzzerControl = EBuzzerControl.ReaderControl
                    return EReaderResult.RT_OK
                else:
                    return EReaderResult.RT_FAILED_ERR
            elif key == EReaderEnum.RW_ReaderStateLED:
                #   查LED灯
                readerLEDModel = val
                result = self.__readerConfig.GetReaderStateLED(self.__connID)
                if result.startswith("0"):
                    readerLEDModel.LEDSwitch = False
                    return EReaderResult.RT_OK
                elif result.startswith("1"):
                    readerLEDModel.LEDSwitch = True
                    readerLEDModel.LEDTime = int(result.rstrip(",").split(",")[1])
                    return EReaderResult.RT_OK
                else:
                    return EReaderResult.RT_INVALID_PARA_ERR
            elif key == EReaderEnum.RW_ReaderDataOutputFormat:
                #   查输出格式
                readerDataOutputModel = val
                result = self.__readerConfig.GetDataOutputFormat(self.__connID)
                dataOutputList = result.rstrip("|").split("|")
                if len(dataOutputList) < 6:
                    return EReaderResult.RT_FAILED_ERR
                # 特殊格式输出开关 | 数据输出格式 | 输出数据类型 | 数据帧头 | 保留 | 保留 | 数据帧尾 | 1, 数据区域
                readerDataOutputModel.outputSwitch = EOutputSwitch(int(dataOutputList[0]))
                readerDataOutputModel.outputFormat = EOutputFormat(int(dataOutputList[1]))
                eReadBank = EReadBank(int(dataOutputList[2]))
                startlen = int(dataOutputList[3][3:4])
                if startlen > 0 :
                    readerDataOutputModel.startData = str(dataOutputList[3][4:])
                endlen = int(dataOutputList[6][3:4])
                if endlen > 0:
                    readerDataOutputModel.endData = str(dataOutputList[6][4:])
                # 可选参数
                if len(dataOutputList) == 8:
                    param = dataOutputList[7].rstrip(",").split(",")[1]
                    len2 = int(hex(int(param[4:6]))[2:])
                    start = hex(int(param[0:4]))[2:]
                    tagDataModel = TagData_Model(eReadBank, int(start), len2, "")
                    readerDataOutputModel.tagData = tagDataModel
                else:
                    tagDataModel = TagData_Model(eReadBank, 0, 0, "")
                    readerDataOutputModel.tagData = tagDataModel
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_ReaderCustomCode:
                #   查自定义编码
                readerStringModel = val
                result = self.__readerConfig.GetCustomCode(self.__connID)
                readerStringModel.data = result
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_ReaderGPIParam:
                readerGPIParamModel = val
                if readerGPIParamModel.GPINum == None:
                    return EReaderResult.RT_INVALID_PARA_ERR
                result = Param_Option.GetReaderGPIParam(self.__connID,str(readerGPIParamModel.GPINum.value))
                gpiList = result.rstrip("|").split("|")
                readerGPIParamModel.triggerStart = ETriggerStart(int(gpiList[0]))
                readerGPIParamModel.customTriggerCode = str(gpiList[1])
                readerGPIParamModel.triggerCode = None
                readerGPIParamModel.triggeerStop = ETriggerStop(int(gpiList[2]))
                readerGPIParamModel.delayTime = int(gpiList[3])
                readerGPIParamModel.isUpload = EGPIUpload(int(gpiList[4]))
                return EReaderResult.RT_OK
            #endregion
            #region RFID配置
            elif key == EReaderEnum.RW_RFIDAntPower:
                readerAntPowerModelList = val
                readerAntPowerModelList.clear()
                dicPower = []
                # 查询功率
                dicPower = self.__readerConfig.GetANTPowerParam(self.__connID)
                # 查询使能
                antPowerList = []
                antPowerStr = self.__readerConfig.GetReaderANT2(self.__connID)
                if not Helper_String.IsNullOrEmpty(antPowerStr):
                    for item in antPowerStr.rstrip(",").split(","):
                        antPowerList.append(int(item))
                for key in dicPower:
                    readerAntPowerModel = ReaderAntPower_Model()
                    readerAntPowerModel.antennaNo = EAntennaNo.getValue(key)
                    readerAntPowerModel.power = dicPower[key]
                    # 已有使能中是否包含，是为true，否为false
                    if antPowerList.__contains__(key) :
                        readerAntPowerModel.enable = True
                    else:
                        readerAntPowerModel.enable = False
                    readerAntPowerModelList.append(readerAntPowerModel)
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_RFIDRF:
                #   查频段
                readerRF__model = val
                readerRF__model2 = self.getRF()
                readerRF__model.RFHoppingMode = readerRF__model2.RFHoppingMode
                readerRF__model.readerWorkFrequency = readerRF__model2.readerWorkFrequency
                readerRF__model.readerWorkPoint = readerRF__model2.readerWorkPoint
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_RFIDEpcBasebandParam:
                #   查基带参数
                epcBasebandModel = val
                result = self.__readerConfig.GetEPCBasebandParam(self.__connID)
                epcStr = result.rstrip("|").split("|")
                epcBasebandModel.eBasebandRate = EBasebandRate(int(epcStr[0]))
                epcBasebandModel.qValue = int(epcStr[1])
                epcBasebandModel.session = int(epcStr[2])
                epcBasebandModel.searchType = ESearchType(int(epcStr[3]))
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_RFIDEpcBaseExpandBandParam:
                #   查基带扩展参数
                extendParam = val
                tagExtendParam = extendParam.TagExtendedParam
                DNQExtendedParam = extendParam.DNQExtendedParam
                ASTExtendedParam = extendParam.ASTExtendedParam
                ASTExtendedParam2 = extendParam.ASTExtendedParam2
                LBTExtendedParam = extendParam.LBTExtendedParam

                result = self.__readerConfig.GetEPCBaseExpandBandParam(self.__connID)
                strs = result.rstrip("&").split("&")
                for i in range(0,len(strs)):
                    tempstrs = strs[i].rstrip(",").split(",")
                    values = Helper_String.hexStringToBytes(tempstrs[1])
                    if tempstrs[0] == "1":
                        tagExtendParam.NXP_Fast_ID = (values[1] & 0x01) != 0
                        tagExtendParam.IMJ_Tag_Focus = (values[3] & 0x10) != 0
                        tagExtendParam.IMJ_Fast_Id = (values[3] & 0x20) != 0
                    elif tempstrs[0] == "2":
                        DNQExtendedParam.maxQ = values[0] & 0xff
                        DNQExtendedParam.minQ = values[1] & 0xff
                        DNQExtendedParam.tmult = values[2] & 0xff
                        DNQExtendedParam.autoQ = (values[3] & 0x01) != 0
                        DNQExtendedParam.forceQ = (values[3] & 0x02) != 0
                    elif tempstrs[0] == "3":
                        ASTExtendedParam.antSwitchMode = EASTSwitchMode(values[0] & 0xff)
                        ASTExtendedParam.retry = values[1] & 0xff
                        ASTExtendedParam.residenceTime = int(Helper_String.GetU16ByBytes(values, 2))
                    elif tempstrs[0] == "4":
                        ASTExtendedParam2.waitingTime = values[0] & 0xff
                        ASTExtendedParam2.antStep = values[1] & 0xff
                        ASTExtendedParam2.antThreshold = values[2] & 0xff
                    elif tempstrs[0] == "5":
                        LBTExtendedParam.workMode = ELBTWorkMode(values[0] & 0xff)
                        LBTExtendedParam.maxRSSI =values[1] & 0xff
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_RFIDTagUploadParam:
                #   查标签上传参数
                readerTagUpdateModel = val
                result = self.__readerConfig.GetTagUpdateParam(self.__connID)
                if result.startswith("-"):
                    return EReaderResult.RT_FAILED_ERR
                tagUpdateList = result.rstrip("|").split("|")
                readerTagUpdateModel.repeatTimeFilter = int(tagUpdateList[0])
                readerTagUpdateModel.rssiFilter = int(tagUpdateList[1])
                if len(tagUpdateList) == 3:
                    readerTagUpdateModel.dBmFilter = int(tagUpdateList[2])
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_RFIDAutoIdleParam:
                #   查自动空闲模式
                readerAutoSleepModel = val
                result = self.__readerConfig.GetReaderAutoSleepParam(self.__connID)
                if result.startswith("Error"):
                    return EReaderResult.RT_FAILED_ERR
                elif result.startswith("Close"):
                    readerAutoSleepModel.autoIdleSwitch = False
                elif result.startswith("Open"):
                    readerAutoSleepModel.autoIdleSwitch = True
                    result = result.rstrip("|").split("|")[1]
                    readerAutoSleepModel.time = int(result)
                return EReaderResult.RT_OK
            #endregion

            #region 读写、临时配置
            elif key == EReaderEnum.WO_RFIDWorkingAnt:
                #   设置工作天线
                readerAnts = val
                readerAnts.antennaList = self.__readerAnt.antennaList
                return EReaderResult.RT_OK
            elif key == EReaderEnum.WO_RFIDReadExtended:
                #   读扩展区
                readExtendedAreaModels = val
                readExtendedAreaModels.clear()
                for key in self.__readExtendedAreaList:
                    readExtendedAreaModels.append(self.__readExtendedAreaList[key])
                return EReaderResult.RT_OK
            elif key == EReaderEnum.WO_RFIDReadSpecial:
                #   设置读特殊区
                readSpecialList = val
                readSpecialList.clear()
                for eReadSpecial in  self.__readSpecialHashSet:
                    readSpecialList.append(eReadSpecial)
                return EReaderResult.RT_OK
            elif key == EReaderEnum.WO_RFIDReadTagFilter:
                #   设置过滤
                tagFilterModels = val
                tagFilterModels.clear()
                for key in self.__tagFilterList:
                    tagFilterModels.append(self.__tagFilterList[key])
                return EReaderResult.RT_OK
            #endregion
            else:
                #   没有对应的查询则返回报错
                val = None
                return EReaderResult.RT_NOT_SUPPORTED_ERR
        except Exception as e:
            val = None
            return EReaderResult.RT_SYSTEM_ERR

    #   读写器配置
    #
    #      @param key
    #      @param val
    def paramSet(self,key,val):
        #   没有connID
        if Helper_String.IsNullOrEmpty(self.__connID):
            return EReaderResult.RT_NOT_CONNECT_ERR
        try:
            #region Reader配置
            if key == EReaderEnum.RW_ReaderSerialPortParam:
                readerSerialModel = val
                resultCode = self.__readerConfig.SetReaderSerialPortParam(self.__connID, readerSerialModel.baudrate)
                result = str(resultCode)
                return self.getTranferHandle(result)
            elif key == EReaderEnum.RW_Reader485Param:
                readerSerialModel1 = val
                strParam = ""
                strParam += str(readerSerialModel1.address)
                strParam += "|1,"
                strParam += str(readerSerialModel1.baudrate.value)
                resultCode = self.__readerConfig.SetReader485(self.__connID, strParam)
                return self.getTranferHandle(str(resultCode))
            elif key == EReaderEnum.RW_ReaderNetwork:
                readerNetWorkModel = val
                # 是否配置DHCP
                self.__readerConfig.SetDHCP(self.__connID, readerNetWorkModel.DhcpSwitch)
                if not readerNetWorkModel.DhcpSwitch:
                    if (not Helper_String.IsIP(readerNetWorkModel.Ipv4Address)) or (not Helper_String.IsIP(readerNetWorkModel.Ipv4Mask)) or (not Helper_String.IsIP(readerNetWorkModel.Ipv4GateWay)):
                        return EReaderResult.RT_INVALID_PARA_ERR

                    readerNetWorkParam = readerNetWorkModel.getReaderNetWorkParam()
                    result = Param_Option.SetReaderNetworkPortParam(self.__connID, readerNetWorkParam)
                    return self.getTranferHandle(result)
                else:
                    return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_ReaderTime:
                readerTimeModel = val
                result = "0"
                if readerTimeModel.UTC != None:
                    result = str(self.__readerConfig.SetReaderUTC(self.__connID, readerTimeModel.UTC))
                    if self.getTranferHandle(result) != EReaderResult.RT_OK:
                        return self.getTranferHandle(result)
                # 设置NTP
                if readerTimeModel.NTP_Switch != None:
                    if readerTimeModel.NTP_Switch:
                        result = Param_Option.SetReaderNTP(self.__connID, "1|" + readerTimeModel.IP)
                    else:
                        result = Param_Option.SetReaderNTP(self.__connID, "0")
                return self.getTranferHandle(result)
            elif key == EReaderEnum.RW_ReaderWorkMode:
                readerWorkModeModel = val
                if readerWorkModeModel.workMode == EWorkMode.Server:
                    resultCode = self.__readerConfig.SetReaderServerOrClient(self.__connID,
                                                                             readerWorkModeModel.workMode,
                                                                             readerWorkModeModel.ip,
                                                                             str(readerWorkModeModel.port))
                elif readerWorkModeModel.workMode == EWorkMode.Client:
                    resultCode = self.__readerConfig.SetReaderServerOrClient(self.__connID,
                                                                             readerWorkModeModel.workMode,
                                                                             readerWorkModeModel.ip,
                                                                             str(readerWorkModeModel.port))
                else:
                    return EReaderResult.RT_INVALID_PARA_ERR
                return self.getTranferHandle(str(resultCode))
            elif key == EReaderEnum.RW_ReaderBreakPointUpload:
                #   设置断点续传
                readerBooleanModel = val
                resultCode = self.__readerConfig.SetBreakPointUpload(self.__connID, readerBooleanModel.flag)
                return self.getTranferHandle(str(resultCode))
            elif key == EReaderEnum.RW_ReaderBuzzerSwitch:
                #   设置蜂鸣器
                readerBuzzerModel = val
                result = "0"
                if readerBuzzerModel.buzzerControl == EBuzzerControl.PCControl:
                    result = Param_Option.SetBuzzerSwitch(self.__connID, "1")
                    if self.getTranferHandle(result) != EReaderResult.RT_OK:
                        return EReaderResult.RT_INVALID_PARA_ERR
                elif readerBuzzerModel.buzzerControl == EBuzzerControl.ReaderControl:
                    result = Param_Option.SetBuzzerSwitch(self.__connID, "0")
                    if self.getTranferHandle(result) != EReaderResult.RT_OK:
                        return EReaderResult.RT_INVALID_PARA_ERR
                buzzerParam = ""
                if readerBuzzerModel.buzzerSwitch != None and readerBuzzerModel.buzzerType != None:
                    if readerBuzzerModel.buzzerSwitch:
                        buzzerParam += "01"
                    else:
                        buzzerParam += "00"
                    if readerBuzzerModel.buzzerType == EBuzzerType.Always:
                        buzzerParam += "01"
                    else:
                        buzzerParam += "00"
                    result = Param_Option.SetBuzzerControl(self.__connID, buzzerParam)
                return self.getTranferHandle(result)
            elif key == EReaderEnum.RW_ReaderStateLED:
                readerLEDModel = val
                if readerLEDModel.LEDSwitch:
                    result = Param_Option.SetReaderStateLED(self.__connID, "1|1," + str(readerLEDModel.LEDTime))
                else:
                    result = Param_Option.SetReaderStateLED(self.__connID, "0")
                return self.getTranferHandle(result)
            elif key == EReaderEnum.RW_ReaderDataOutputFormat:
                #   设置输出格式
                readerDataOutputModel = val
                if readerDataOutputModel.tagData == None:
                    return EReaderResult.RT_INVALID_PARA_ERR
                if readerDataOutputModel.tagData.tagStart == None:
                    # 为空的话
                    result = self.__readerConfig.SetDataOutputFormat(self.__connID,
                                                                     str(readerDataOutputModel.outputSwitch.value),
                                                                     str(readerDataOutputModel.outputFormat.value),
                                                                     str(readerDataOutputModel.tagData.Bank.value),
                                                                     str(readerDataOutputModel.startData),
                                                                     str(readerDataOutputModel.endData),None,None)
                else:
                    result = self.__readerConfig.SetDataOutputFormat(self.__connID,
                                                         str(readerDataOutputModel.outputSwitch.value),
                                                         str(readerDataOutputModel.outputFormat.value),
                                                         str(readerDataOutputModel.tagData.Bank.value),
                                                         str(readerDataOutputModel.startData),
                                                         str(readerDataOutputModel.endData),
                                                         str(readerDataOutputModel.tagData.tagStart),
                                                         str(readerDataOutputModel.tagData.tagLen))
                return self.getTranferHandle(result)
            elif key == EReaderEnum.RW_ReaderCustomCode:
                #   设置自定义编码
                readerStringModel = val
                result = self.__readerConfig.SetCustomCode(self.__connID, readerStringModel.data)
                return self.getTranferHandle(result)
            elif key == EReaderEnum.RW_ReaderGPIParam:
                readerGPIParamModel = val
                resultCode = self.__readerConfig.SetReaderGPIParam(self.__connID, readerGPIParamModel.GPINum,
                                                            readerGPIParamModel.triggerStart,
                                                            readerGPIParamModel.triggerCode,
                                                            readerGPIParamModel.triggeerStop,
                                                            str(readerGPIParamModel.delayTime),
                                                            readerGPIParamModel.isUpload,
                                                            readerGPIParamModel.customTriggerCode)
                return self.getTranferHandle(str(resultCode))
            #endregion
            #region RFID配置
            elif key == EReaderEnum.RW_RFIDAntPower:
                #   设置天线功率
                readerAntPowerModelList = val
                dicPower = {}
                antPowerList = []
                for readerAntPowerModel in readerAntPowerModelList:
                    if readerAntPowerModel.antennaNo == None:
                        return EReaderResult.RT_INVALID_PARA_ERR
                    if readerAntPowerModel.power != None:
                        dicPower[EAntennaNo.getIndex(readerAntPowerModel.antennaNo)] = readerAntPowerModel.power
                    if readerAntPowerModel.enable != None and readerAntPowerModel.enable:
                        antPowerList.append(EAntennaNo.getIndex(readerAntPowerModel.antennaNo))
                resultCode = -1
                if len(dicPower) != 0:
                    resultCode = self.__readerConfig.SetANTPowerParam(self.__connID, dicPower)
                    if resultCode != 0:
                        return self.getTranferHandle(str(resultCode))
                if len(antPowerList) != 0 :
                    antNum = self.getAntNum(antPowerList)
                    resultCode = self.__readerConfig.SetReaderANT(self.__connID, antNum)
                    if resultCode != 0:
                        return self.getTranferHandle(str(resultCode))
                if resultCode == -1:
                    return EReaderResult.RT_INVALID_PARA_ERR
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_RFIDRF:
                #   设置频段
                readerRF__model = val
                result = "-1"
                # 配置频段
                if readerRF__model.readerWorkFrequency != None:
                    result = RFID_Option.SetReaderRF(self.__connID, readerRF__model.readerWorkFrequency.value)
                    if self.getTranferHandle(result) !=  EReaderResult.RT_OK:
                        return self.getTranferHandle(result)
                # 配置频点
                if readerRF__model.RFHoppingMode != None:
                    if readerRF__model.RFHoppingMode == EWF_Mode.Auto:
                        result = RFID_Option.SetReaderWorkFrequency(self.__connID, "1")
                        if self.getTranferHandle(result) != EReaderResult.RT_OK:
                            return self.getTranferHandle(result)
                    else:
                        rfParam = "0|"
                        for rfItem in  readerRF__model.readerWorkPoint:
                            rfParam += str(rfItem) + ","
                        rfParam = rfParam.rstrip( ',')
                        result = RFID_Option.SetReaderWorkFrequency(self.__connID, rfParam)
                        if self.getTranferHandle(result) != EReaderResult.RT_OK:
                            return self.getTranferHandle(result)
                if result.startswith("-1"):
                    return EReaderResult.RT_INVALID_PARA_ERR
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_RFIDEpcBasebandParam:
                #   设置基带参数
                epcBasebandModel = val
                resultCode = self.__readerConfig.SetEPCBasebandParam(self.__connID,
                                                                     epcBasebandModel.eBasebandRate.value,
                                                                     epcBasebandModel.qValue,
                                                                     epcBasebandModel.session,
                                                                     epcBasebandModel.searchType.value)
                if resultCode != 0 :
                    return self.getTranferHandle(str(resultCode))
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_RFIDEpcBaseExpandBandParam:
                #   设置基带扩展参数
                extendParam = val
                tagExtendParam = extendParam.TagExtendedParam
                DNQExtendedParam = extendParam.DNQExtendedParam
                ASTExtendedParam = extendParam.ASTExtendedParam
                ASTExtendedParam2 = extendParam.ASTExtendedParam2
                LBTExtendedParam = extendParam.LBTExtendedParam
                param = ""
                tempParam = ""
                #  TAG
                tag = 0
                if tagExtendParam.IMJ_Tag_Focus:
                    tag |= 1 << 4
                if tagExtendParam.IMJ_Fast_Id:
                    tag |= 1 << 5
                if tagExtendParam.NXP_Fast_ID:
                    tag |= 1 << 16
                tempParam =  "{:08X}".format(tag)
                param += "1," + tempParam
                # DQN 02
                dnq = 0
                dnq |= (DNQExtendedParam.maxQ & 0xff) << 24
                dnq |= (DNQExtendedParam.minQ & 0xff) << 16
                dnq |= (DNQExtendedParam.tmult & 0xff) << 8
                if DNQExtendedParam.autoQ:
                    dnq |= 0x1
                else:
                    dnq |= 0
                if DNQExtendedParam.forceQ:
                    dnq |= 0x2
                else:
                    dnq |= 0
                tempParam = "{:08X}".format(dnq)
                param += "&2," + tempParam

                # AST 03
                if ASTExtendedParam.retry != None  or  ASTExtendedParam.residenceTime != None:
                    ast = 0
                    ast |= (ASTExtendedParam.antSwitchMode.value & 0xff) << 24

                    if ASTExtendedParam.retry != None:
                        ast |= (int(ASTExtendedParam.retry) & 0xff) << 16

                    if ASTExtendedParam.residenceTime != None:
                        ast |= (int(ASTExtendedParam.residenceTime) & 0xffff)
                    tempParam = "{:08X}".format(ast)
                    param += "&3," + tempParam
                # AST2 04
                if ASTExtendedParam2.waitingTime != None and ASTExtendedParam2.antStep != None:
                    ast = 0
                    if ASTExtendedParam2.waitingTime != None:
                        ast |= (int(ASTExtendedParam2.waitingTime)& 0xff) << 24
                    if ASTExtendedParam2.antStep != None:
                        ast |= (int(ASTExtendedParam2.antStep) & 0xff) << 16
                    if ASTExtendedParam2.antThreshold != None:
                        ast |= (int(ASTExtendedParam2.antThreshold) & 0xff) << 8
                    # AST 4
                    tempParam = "{:08X}".format(ast)
                    param += "&4," + tempParam

                # LBT 05
                if LBTExtendedParam.maxRSSI != None:
                    lbt = 0
                    lbt |= (LBTExtendedParam.workMode.value & 0xff) << 24
                    if LBTExtendedParam.maxRSSI != None:
                        lbt |= (int(LBTExtendedParam.maxRSSI) & 0xff) << 16
                    tempParam = "{:08X}".format(lbt)
                    param += "&5," + tempParam
                result = self.__readerConfig.SetEPCBaseExpandBandParam(self.__connID, param)
                return self.getTranferHandle(result)
            elif key == EReaderEnum.RW_RFIDTagUploadParam:
                readerTagUpdateModel = val
                if readerTagUpdateModel.dBmFilter != None and readerTagUpdateModel.dBmFilter() != 0:
                    resultCode = self.__readerConfig.SetTagUpdateParam(self.__connID,
                                                                       readerTagUpdateModel.repeatTimeFilter,
                                                                       readerTagUpdateModel.rssiFilter,
                                                                       readerTagUpdateModel.dBmFilter)
                else:
                    resultCode = self.__readerConfig.SetTagUpdateParam(self.__connID,
                                                                       readerTagUpdateModel.repeatTimeFilter,
                                                                       readerTagUpdateModel.rssiFilter,None)
                if resultCode != 0 :
                    return self.getTranferHandle(str(resultCode))
                return EReaderResult.RT_OK
            elif key == EReaderEnum.RW_RFIDAutoIdleParam:
                #   设置自动空闲模式
                readerAutoSleepModel = val
                if readerAutoSleepModel.autoIdleSwitch:
                    resultCode = self.__readerConfig.SetReaderAutoSleepParam(self.__connID, readerAutoSleepModel.autoIdleSwitch, str(readerAutoSleepModel.time))
                else:
                    resultCode = self.__readerConfig.SetReaderAutoSleepParam(self.__connID, readerAutoSleepModel.autoIdleSwitch, "")
                if resultCode != 0:
                    return self.getTranferHandle(resultCode.toString())
                return EReaderResult.RT_OK
            # endregion
            #region 读配置
            elif key == EReaderEnum.WO_RFIDWorkingAnt:
                readerAnts = val
                self.__readerAnt.antennaList = readerAnts.antennaList
                return EReaderResult.RT_OK
            elif key == EReaderEnum.WO_RFIDReadExtended:
                readExtendedAreaModels = val
                self.__readExtendedAreaList.clear()
                if readExtendedAreaModels == None or len(readExtendedAreaModels) == 0 :
                    return EReaderResult.RT_OK
                for readExtendedAreaModel in  readExtendedAreaModels:
                    if readExtendedAreaModel.bank == None or readExtendedAreaModel.bank == EReadBank.EPC:
                        return EReaderResult.RT_INVALID_PARA_ERR
                    self.__readExtendedAreaList[readExtendedAreaModel.bank] =  readExtendedAreaModel
                return EReaderResult.RT_OK
            elif key == EReaderEnum.WO_RFIDReadSpecial:
                readSpecialList = val
                self.__readSpecialHashSet.clear()
                for eReadSpecial in  readSpecialList:
                    self.__readSpecialHashSet.append(eReadSpecial)
                return EReaderResult.RT_OK
            elif key == EReaderEnum.WO_RFIDReadTagFilter:
                tagFilterModels = val
                self.__tagFilterList.clear()
                if tagFilterModels == None or len(tagFilterModels) == 0:
                    return EReaderResult.RT_OK
                for tagFilterModel in  tagFilterModels:
                    if tagFilterModel.Bank == None or tagFilterModel.Bank == EReadBank.EpcData or tagFilterModel.Bank == EReadBank.Reserved:
                        return EReaderResult.RT_INVALID_PARA_ERR
                    self.__tagFilterList[tagFilterModel.Bank] = tagFilterModel
                return EReaderResult.RT_OK
            elif key == EReaderEnum.WO_SetGPOState:
                readerGPOStateModel = val
                # 照搬ReaderConfig.SetReaderGPOState，因为代码隔离的原因，原方法需要rfidread中的枚举，不适用本场景。
                rt = -1
                paramStr = ""
                for key in readerGPOStateModel.dicState:
                    paramStr += str(key.value+1) + "," + str(readerGPOStateModel[key].value)
                    paramStr += "&"
                paramStr = paramStr.rstrip("&")
                rtStr = Param_Option.SetReaderGPOState(self.__connID, paramStr)
                rt = RFIDReader.GetReturnData(rtStr)
                return self.getTranferHandle(str(rt))
            # endregion
            else:
                # 没有对应的查询则返回报错
                val = None
                return EReaderResult.RT_NOT_SUPPORTED_ERR
        except Exception as e:
            val = None
            return EReaderResult.RT_SYSTEM_ERR

    #   连接读写器
    def connectReader(self,param,log):
        flag = False
        try:
            if param.startswith("Serial:"):
                param = param[len("Serial:"):]
                flag = RFIDReader.CreateSerialConn(param, self)
            elif param.startswith("RS232:"):
                param = param[len("RS232:"):]
                flag = RFIDReader.CreateSerialConn(param, self)
            elif param.startswith("RS485:"):
                param = param[len("RS485:"):]
                flag = RFIDReader.Create485Conn(param, self)
            elif param.startswith("TCP:"):
                param = param[len("TCP:"):]
                flag = RFIDReader.CreateTcpConn(param, self)
            elif param.startswith("USB:"):
                param = param[len("USB:"):]
                flag = RFIDReader.CreateUsbConn(param, self)
            if flag:
                if log != None and self.getInitFlag():
                    self.__IAsynchHash[param] = log
                self.__connID = param
            return flag
        except Exception as e:
            print("错误信息%s" % e)
            return False

    #   关闭单个连接
    def closeConnect(self):
        RFIDReader.CloseConn(self.__connID)
        if self.__connID in self.__IAsynchHash:
            del(self.__IAsynchHash[self.__connID])
        self.__connID = ""

    #   开启TCP服务监听
    def openTcpServer(self,serverIP, serverPort,log):
        self.__IAsynchHash[self.__listenConnID] = log
        return RFIDReader.OpenTcpServer(serverIP, str(serverPort), self)

    #   关闭TCP服务监听
    def closeTcpServer(self):
        if self.__listenConnID in self.__IAsynchHash:
            del(self.__IAsynchHash[self.__listenConnID])
        RFIDReader.CloseTcpServer()

    #   获得服务器是否正在监听
    def getServerStartUp(self):
        return RFIDReader.GetServerStartUp()

    #   开启搜索设备
    def startSearchDevice(self,msg):
        self.__ISearchHash[self.__listenConnID] =  msg
        return RFIDReader.StartSearchDevice(self)

    #   关闭搜索设备
    def stopSearchDevice(self):
        if self.__ISearchHash[self.__listenConnID] != None:
            del(self.__ISearchHash[self.__listenConnID])
        RFIDReader.StopSearchDevice()

    #   获取USB设备列表
    @staticmethod
    def getUsbHidDeviceList():
        return RFIDReader.GetUsbHidDeviceList()

    #region  读写器操作(重启、恢复出厂)
    #   重启读写器
    def restartReader(self):
        self.__readerConfig.ReSetReader(self.__connID)

    #   恢复出厂设置
    def setReaderRestoreFactory(self):
        if self.__readerConfig.SetReaderRestoreFactory(self.__connID) != 0:
            return EReaderResult.RT_FAILED_ERR
        else:
            return EReaderResult.RT_OK
    #endregion

    #region 盘点和停止读
    #   异步、开启盘点
    def inventory(self):
        # 获取用户自定义编码
        readerString = ReaderString_Model()
        self.paramGet(EReaderEnum.RW_ReaderCustomCode, readerString)
        Tag_Model.CustomID = readerString.data

        readerStringModel = ReaderString_Model()
        readerResult = self.getInventoryParam(readerStringModel)
        if readerResult != EReaderResult.RT_OK:
            return readerResult
        try :
            self.stop()
            rt = RFID_Option.GetEPC(self.__connID, readerStringModel.data)
            return self.getTranferHandle(rt)
        except Exception as e:
            print("方法inventory失败，错误信息%s" % e)
            return EReaderResult.RT_SYSTEM_ERR

    #   传入回调接口，盘点
    def inventorySync(self,log):
        # 获取用户自定义编码
        readerString = ReaderString_Model()
        self.paramGet(EReaderEnum.RW_ReaderCustomCode, readerString)
        Tag_Model.CustomID = readerString.data

        initFlag = True
        self.__IAsynchHash[self.__connID] = log
        RFIDReader.HP_CONNECT[self.__connID].myLog = self
        return self.inventory()

    #   同步、开启盘点
    #   param milliseconds 读取时间，毫秒
    #   param val 返回数据List<Tag_Model>
    def read(self,milliseconds,val):
        if self.__initFlag:
            return EReaderResult.RT_NOT_SUPPORTED_ERR
        # 获取用户自定义编码
        readerString = ReaderString_Model()
        self.paramGet(EReaderEnum.RW_ReaderCustomCode, readerString)
        Tag_Model.CustomID = readerString.data

        readerStringModel = ReaderString_Model()
        readerResult = self.getInventoryParam(readerStringModel)
        if readerResult != EReaderResult.RT_OK :
            return readerResult
        try:
            self.stop()
            self.__tagModelList.clear()
            rt = RFID_Option.GetEPC(self.__connID, readerStringModel.data)
            if not rt.startswith("0"):
                return self.getTranferHandle(rt)
            sleep(milliseconds/1000)
            self.stop()
            tag_models = val
            tag_models.clear()
            tag_models.extend(self.__tagModelList)
            self.__tagModelList.clear()
        except Exception as e:
            return EReaderResult.RT_SYSTEM_ERR
        return EReaderResult.RT_OK

    #   停止读
    def stop(self):
        if self.__readerConfig.Stop(self.__connID) == 0:
            return EReaderResult.RT_OK
        else:
            return EReaderResult.RT_FAILED_ERR
    #endregion

    #region 写、锁、毁

    #       写标签
    #      * @param setWritingRules 写入规则(写入区域，写入起始下标，写入数据)
    #      * @param matchFilter 过滤规则（匹配bank区域，匹配数据起始下标，匹配数据）
    def writeTag(self,setWritingRules,matchFilter,passWord):
        try:
            #region 必选参数
            param = ""
            param += self.getAntNumParam() + "|"
            if setWritingRules.Bank == EReadBank.Reserved:
                param += "0|"
            elif setWritingRules.Bank == EReadBank.EPC:
                param += "1|"
            elif setWritingRules.Bank == EReadBank.TID:
                param += "2|"
            elif setWritingRules.Bank == EReadBank.UserData:
                param += "3|"
            elif setWritingRules.Bank == EReadBank.EpcData:
                return EReaderResult.RT_INVALID_PARA_ERR
            # 起始位置 + 写入字符
            if int(setWritingRules.tagStart) == 2:
                # 写EPC时，同时把前面的PC值写上，
                param += "0001|"
                iLen = len(setWritingRules.data) / 4 if len(setWritingRules.data) % 4 == 0 else (len(setWritingRules.data) / 4) + 1
                iLen = int(iLen)
                i_PC = iLen << 11
                s_PC = hex(i_PC)[2:].rjust(4, '0')
                s_EPC = (s_PC + setWritingRules.data).ljust((iLen + 1) * 4, '0')
                param += s_EPC + "|"
            else:
                param += str(setWritingRules.tagStart).rjust(4, '0') + "|"
                param_2 = setWritingRules.data
                if len(param_2) % 2 != 0:
                    param_2 += "0"
                param += param_2 + "|"


            #endregion
            #region 可选参数
            filterParam = ""
            if matchFilter != None:
                if matchFilter.Bank == EReadBank.Reserved:
                    filterParam += ""
                elif matchFilter.Bank == EReadBank.EPC:
                    filterParam += "1,"
                    filterParam += "1".rjust(2, '0')
                    filterParam += (hex(matchFilter.tagStart)[2:]).rjust(4, '0')
                    filterParam += Helper_String.ByteToStringOne(len(matchFilter.data) * 4)
                    if Helper_String.IsNullOrEmpty(matchFilter.data):
                        filterParam += ""
                    else:
                        filterParam += matchFilter.data
                    filterParam += "&"
                elif matchFilter.Bank == EReadBank.TID:
                    filterParam += "1,"
                    filterParam += "2".rjust(2, '0')
                    filterParam += str(matchFilter.tagStart).rjust(4, '0')
                    filterParam += Helper_String.ByteToStringOne(len(matchFilter.data) * 4)
                    if Helper_String.IsNullOrEmpty(matchFilter.data):
                        filterParam += ""
                    else:
                        filterParam += matchFilter.data
                    filterParam += "&"
                elif matchFilter.Bank == EReadBank.UserData:
                    filterParam += "1,"
                    filterParam += "3".rjust(2, '0')
                    filterParam += str(matchFilter.tagStart).rjust(4, '0')
                    filterParam += Helper_String.ByteToStringOne(len(matchFilter.data) * 4)
                    if Helper_String.IsNullOrEmpty(matchFilter.data):
                        filterParam += ""
                    else:
                        filterParam += matchFilter.data
                    filterParam += "&"
                else:
                    filterParam += ""

            param += filterParam
            if not Helper_String.IsNullOrEmpty(passWord):
                param += "2," + passWord.strip() + "&"

            # 大于天线8
            addAntParam = self.getAddAntParam()
            PID = "4"
            if  addAntParam != "0000":
                param += (PID + "," + addAntParam + "&")
            param = param.rstrip('&')
            # endregion
            param = param.rstrip('|')
            strData = RFID_Option.WriteEPC(self.__connID, param)
            if not strData.startswith("0"):
                if strData.startswith("7"):
                    return EReaderResult.RT_AREA_LOCKED_ERR
                elif strData.startswith("10"):
                    return EReaderResult.RT_TAG_LOSS_ERR
                else:
                    return EReaderResult.RT_FAILED_ERR
            return EReaderResult.RT_OK
        except Exception as e:
            print("方法writeTag失败，错误信息%s" % e)
            return EReaderResult.RT_SYSTEM_ERR

    #      锁标签
    #      * @param lockArea 锁区域
    #      * @param lockType 锁类型
    #      * @param filter 过滤器
    #      * @param passWord 密码
    def lockTag(self,lockArea, lockType, filter, passWord):
        try:
            param = ""
            param += self.getAntNumParam() + "|"
            param += str(lockArea.value) + "|"
            param += str(lockType.value) + "|"
            #   必选参数结束
            #region  可选参数
            filterParam = self.getFilterParam(filter)
            param += filterParam

            if not Helper_String.IsNullOrEmpty(passWord):
                param += "2," + passWord.strip() + "&"

            # 大于天线8
            addAntParam = self.getAddAntParam()
            PID = "3"

            if  addAntParam != "0000":
                param += (PID + "," + addAntParam + "&")
            param = param.rstrip('&')
            #endregion
            param = param.rstrip('|')
            strData = RFID_Option.LockEPC(self.__connID, param)
            if not strData.startswith("0"):
                if strData.startswith("7"):
                    return EReaderResult.RT_AREA_LOCKED_ERR
                if strData.startswith("10"):
                    return EReaderResult.RT_TAG_LOSS_ERR
                return EReaderResult.RT_FAILED_ERR
            return EReaderResult.RT_OK
        except Exception as e:
            print("方法lockTag失败，错误信息%s" % e)
            return EReaderResult.RT_SYSTEM_ERR

    #      毁标签
    #      * @param filter 过滤器
    #      * @param passWord 密码
    def destroyTag(self,filter, passWord):
        try:
            param = ""
            param += self.getAntNumParam() + "|"
            param += passWord + "|"
            #   必选参数结束
            # region  可选参数
            filterParam = self.getFilterParam(filter)
            param += filterParam

            # 大于天线8
            addAntParam = self.getAddAntParam()
            PID = "3"
            if addAntParam != "0000":
                param += (PID + "," + addAntParam + "&")
            param = param.rstrip('&')
            # endregion
            param = param.rstrip('|')
            print(param)
            strData = RFID_Option.DestroyEPC(self.__connID, param)
            if not strData.startswith("0"):
                if strData.startswith("5"):
                    return EReaderResult.RT_TAG_DESTORY_PASS_ERR
                if strData.startswith("7"):
                    return EReaderResult.RT_TAG_LOSS_ERR
                return EReaderResult.RT_FAILED_ERR
            return EReaderResult.RT_OK
        except Exception as e:
            print("方法destroyTag失败，错误信息%s" % e)
            return EReaderResult.RT_SYSTEM_ERR
    #endregion

    #region 获取标签数据
    def getTagData(self):
        tag_models = []
        tag_models.extend(self.__tagModelList)
        self.__tagModelList.clear()
        return tag_models
    # endregion

    #region 断点续传
    #   获取断点续传（异步）
    def inventoryCacheTag(self):
        if  not self.__initFlag:
            return EReaderResult.RT_NOT_SUPPORTED_ERR

        Result = Param_Option.GetBreakPointCacheTag(self.__connID)
        return EReaderResult.RT_OK

    #   获取断点续传 ，同步转为异步方式
    def inventoryCacheTagSync(self,log):
        initFlag = True
        self.__IAsynchHash[self.__connID] =  log
        RFIDReader.HP_CONNECT[self.__connID].myLog = self
        return self.inventoryCacheTag()

    # 获取断点续传（同步）
    def readCacheTag(self,val):
        if self.__initFlag:
            return EReaderResult.RT_NOT_SUPPORTED_ERR
        try:
            self.stop()
            self.__tagModelList.clear()
            cacheCount = 0
            recordNum = 0
            Result = Param_Option.GetBreakPointCacheTag(self.__connID)
            #   等待一秒，如果读到的缓存数没变，表示读完了缓存，退出循环。   如果读到的缓存和1秒前的值多，则说明还在获取缓存，继续循环。
            while True:
                sleep(1000)
                if recordNum == self.__cacheCount:
                    break
                else:
                    recordNum = cacheCount
            tag_models = val
            tag_models.clear()
            tag_models.append(self.__tagModelList)
            self.__tagModelList.clear()
            return EReaderResult.RT_OK
        except Exception as e:
            print("方法readCacheTag失败，错误信息%s" % e)
            return EReaderResult.RT_SYSTEM_ERR

    #   清空断点缓存
    def clearBreakPointCache(self):
        resultCode = self.__readerConfig.ClearBreakPointCache(self.__connID)
        return self.getTranferHandle(str(resultCode))
    #endregion

    #region 接口
    def WriteDebugMsg(self,connID,msg):
        try:
            #  异步方式，需转发一下
            if connID in self.__IAsynchHash:
                self.__IAsynchHash[connID].WriteDebugMsg(connID, msg)
            return
        except Exception as e:
            print("方法WriteDebugMsg失败，错误信息%s" % e)

    def WriteLog(self,connID,msg):
        try:
            #  异步方式，需转发一下
            if connID in self.__IAsynchHash:
                self.__IAsynchHash[connID].WriteLog(connID, msg)
            return
        except Exception as e:
            print("方法WriteLog失败，错误信息%s" % e)

    def PortConnecting(self,connID):
        try:
            if connID in self.__readerList:
                reader = Reader()
                reader.connID = connID
                self.__readerList[connID] = reader
            # 异步方式，需转发一下
            if connID in self.__IAsynchHash:
                self.__IAsynchHash[connID].PortConnecting(connID)
            elif self.__listenConnID in self.__IAsynchHash:
                self.__IAsynchHash[self.__listenConnID].PortConnecting(connID)
        except Exception as e:
            print("方法WriteLog失败，错误信息%s" % e)

    def PortClosing(self,connID):
        try:
            if connID in self.__readerList:
                del(self.__readerList[connID])
            #   异步方式，需转发一下
            if connID in self.__IAsynchHash:
                self.__IAsynchHash[connID].PortClosing(connID)
            elif self.__listenConnID in self.__IAsynchHash:
                self.__IAsynchHash[self.__listenConnID].PortClosing(connID)
        except Exception as e:
            print("方法PortClosing失败，错误信息%s" % e)

    def OutputTags(self,tag):
        try:
            # 异步方式，需转发一下
            if self.__connID in self.__IAsynchHash:
                self.__IAsynchHash[self.__connID].OutputTags(tag)
                return
            # 同步方式
            if tag == None or tag._Result != 0x00:
                return
            if tag._IsContinue == 1:
                self.__cacheCount += 1
            self.__tagModelList.append(tag)
            self.__tagModelList = list(set(self.__tagModelList))
        except Exception as e:
            print("方法OutputTags失败，错误信息%s" % e)

    def OutputTagsOver(self,connID):
        try:
            # 异步方式，需转发一下
            if connID in self.__IAsynchHash:
                self.__IAsynchHash[connID].OutputTagsOver(connID)
            return
        except Exception as e:
            print("方法OutputTags失败，错误信息%s" % e)

    def GPIControlMsg(self,connID, gpi_model):
        try:
            # 异步方式，需转发一下
            if connID in self.__IAsynchHash:
                self.__IAsynchHash[connID].GPIControlMsg(connID,gpi_model)
            return
        except Exception as e:
            print("方法GPIControlMsg失败，错误信息%s" % e)

    def OutputScanData(self,connID,scandata):
        try:
            # 异步方式，需转发一下
            if connID in self.__IAsynchHash:
                self.__IAsynchHash[connID].OutputScanData(connID,scandata)
            return
        except Exception as e:
            print("方法GPIControlMsg失败，错误信息%s" % e)

    def DeviceInfo(self,model):
        try:
            # 异步方式，需转发一下
            if self.__connID in self.__IAsynchHash:
                self.__IAsynchHash[self.__connID].DeviceInfo(model)
            elif self.__listenConnID in self.__IAsynchHash:
                self.__IAsynchHash[self.__listenConnID].DeviceInfo(model)
            return
        except Exception as e:
            print("方法DeviceInfo失败，错误信息%s" % e)

    def DebugMsg(self,msg):
        try:
            # 异步方式，需转发一下
            if self.__connID in self.__IAsynchHash:
                self.__IAsynchHash[self.__connID].DebugMsg(msg)
            elif self.__listenConnID in self.__IAsynchHash:
                self.__IAsynchHash[self.__listenConnID].DebugMsg(msg)
            return
        except Exception as e:
            print("方法DeviceInfo失败，错误信息%s" % e)
    #endregion

    # region 辅助方法
    #       处理天线，返回对应int，
    #      * @param param 1,2,3
    def getAntNum(self,param):
        try:
            antNum = 0
            for ant in param:
                if ant == 1:
                    antNum += 1
                elif ant == 2:
                    antNum += 2
                elif ant == 3:
                    antNum += 4
                elif ant == 4:
                    antNum += 8
                elif ant == 5:
                    antNum += 16
                elif ant == 6:
                    antNum += 32
                elif ant == 7:
                    antNum += 64
                elif ant == 8:
                    antNum += 128
                elif ant == 9:
                    antNum += 256
                elif ant == 10:
                    antNum += 512
                elif ant == 11:
                    antNum += 1024
                elif ant == 12:
                    antNum += 2048
                elif ant == 13:
                    antNum += 4096
                elif ant == 14:
                    antNum += 8192
                elif ant == 15:
                    antNum += 16384
                elif ant == 16:
                    antNum += 32768
                elif ant == 17:
                    antNum += 65536
                elif ant == 18:
                    antNum += 131072
                elif ant == 19:
                    antNum += 262144
                elif ant == 20:
                    antNum += 524288
                elif ant == 21:
                    antNum += 1048576
                elif ant == 22:
                    antNum += 2097152
                elif ant == 23:
                    antNum += 4194304
                elif ant == 24:
                    antNum += 8388608

            return antNum
        except Exception as e:
            print("方法getAntNum失败，错误信息%s" % e)
            antNum = -1
            return antNum

    #   获得频段频点实体
    def getRF(self):
        readerRF__model = ReaderRF_Model()
        # 处理频段频点
        rtStr = RFID_Option.GetReaderWorkFrequency(self.__connID)
        rt = RFID_Option.GetReaderRF(self.__connID)
        ReaderConfig.InitDIC_RF()
        result = ""
        Rf = rtStr.rstrip("|").split("|")
        RfNum = None
        if len(Rf)== 2:
            if Rf[0]=="0":
                readerRF__model.RFHoppingMode =EWF_Mode.Specified
            else:
                readerRF__model.RFHoppingMode = EWF_Mode.Auto
            RfNum = Rf[1].rstrip(",").split(",")
        rfIndex = int(rt)
        rf_range = ERF_Range(rfIndex)
        readerRF__model.readerWorkFrequency = rf_range
        dicRf = ReaderConfig.getDicRf()
        rfList = []
        for item in RfNum:
            rfList.append(int(item))
        result = result.rstrip(',')
        readerRF__model.readerWorkPoint = rfList
        return readerRF__model

    #   读标签所用的返回天线字符串
    def getAntNumParam(self):
        if self.__readerAnt.antennaList == None :
            return "1"
        antNum = 0
        for i in self.__readerAnt.antennaList:
            if i == 1:
                antNum += EAntennaNo._1.value
            elif i == 2:
                antNum += EAntennaNo._2.value
            elif i == 3:
                antNum += EAntennaNo._3.value
            elif i == 4:
                antNum += EAntennaNo._4.value
            elif i == 5:
                antNum += EAntennaNo._5.value
            elif i == 6:
                antNum += EAntennaNo._6.value
            elif i == 7:
                antNum += EAntennaNo._7.value
            elif i == 8:
                antNum += EAntennaNo._8.value
        return str(antNum)

    #   获取增加天线参数
    def getAddAntParam(self):
        if self.__readerAnt.antennaList == None:
            return "0000"
        antNum = 0
        for i in self.__readerAnt.antennaList:
            if i == 9:
                antNum += EAntennaNo._9.value
            elif i == 10:
                antNum += EAntennaNo._10.value
            elif i == 11:
                antNum += EAntennaNo._11.value
            elif i == 12:
                antNum += EAntennaNo._12.value
            elif i == 13:
                antNum += EAntennaNo._13.value
            elif i == 14:
                antNum += EAntennaNo._14.value
            elif i == 15:
                antNum += EAntennaNo._15.value
            elif i == 16:
                antNum += EAntennaNo._16.value
            elif i == 17:
                antNum += EAntennaNo._17.value
            elif i == 18:
                antNum += EAntennaNo._18.value
            elif i == 19:
                antNum += EAntennaNo._19.value
            elif i == 20:
                antNum += EAntennaNo._20.value
            elif i == 21:
                antNum += EAntennaNo._21.value
            elif i == 22:
                antNum += EAntennaNo._22.value
            elif i == 23:
                antNum += EAntennaNo._23.value
            elif i == 24:
                antNum += EAntennaNo._24.value
        #   这步一定不能少，9-24天线是在协议扩展中
        antNum /= 256
        if antNum != 0:
            return  (hex(antNum)[2:]).rjust(4,'0')
        else:
            return "0000"

    def getHexStringByUInt16(self,iParam):
        rt = ""
        rt = Helper_String.ByteToString(self.getReverseU16(iParam))
        return rt

    def getReverseU16(self,data):
        rt = Helper_String.IntToBytes(data)
        rt = Helper_Protocol.Reverse(rt)
        return rt
    def getHexStringByUInt32(self,iParam):
        rt = Helper_String.ByteToString(self.getReverseU32(iParam))
        return rt
    def getReverseU32(self,data):
        rt = Helper_String.IntToBytes(data)
        rt = Helper_Protocol.Reverse(rt)
        return rt
    def getHexStringByByte(self,iParam):
        rt = Helper_String.ByteToStringOne(iParam)
        return rt

    #region 查询结果转换处理器
    #   将结果和用户对象传入，返回结果
    def getTranferHandle(self,result):
        if result.startswith("0"):
            return EReaderResult.RT_OK
        elif result.startswith("-2"):
            return EReaderResult.RT_TIMEOUT_ERR
        elif result.startswith("-3"):
            return EReaderResult.RT_INVALID_PARA_ERR
        else:
            return EReaderResult.RT_FAILED_ERR

    #       两个对象中相同的属性值复制
    #      * @param rfidTag
    #      * @param rfidreadTag
    def tagCopy(self):
        pass
    #endregion

    #       获得可选参数param
    #      * @param filter 过滤器
    def getFilterParam(self,filter):
        param = ""
        if filter != None:
            if filter.Bank == EReadBank.Reserved:
                return  ""
            elif filter.Bank == EReadBank.EPC:
                param += "1,"
                param += "1".rjust(2, '0')
                param += str(filter.tagStart).rjust(4, '0')
                param += Helper_String.ByteToStringOne(len(filter.data) * 4)
                if Helper_String.IsNullOrEmpty(filter.data):
                    param += ""
                else:
                    param += filter.data
                param += "&"
            elif filter.Bank == EReadBank.TID:
                param += "1,"
                param += "2".rjust(2, '0')
                param += str(filter.tagStart).rjust(4, '0')
                param += Helper_String.ByteToStringOne(len(filter.data) * 4)
                if Helper_String.IsNullOrEmpty(filter.data):
                    param += ""
                else:
                    param += filter.data
                param += "&"
            elif filter.Bank == EReadBank.UserData:
                param += "1,"
                param += "3".rjust(2, '0')
                param += str(filter.tagStart).rjust(4, '0')
                param += Helper_String.ByteToStringOne(len(filter.data) * 4)
                if Helper_String.IsNullOrEmpty(filter.data):
                    param += ""
                else:
                    param += filter.data
                param += "&"
            elif filter.Bank == EReadBank.EpcData:
                return ""

        return param

    #   获取读EPC的param
    def getInventoryParam(self,readerStringModel):
        try:
            param = ""
            # 天线、读取方式
            param += self.getAntNumParam()
            param += "|1|"
            #region 循环过滤器
            if self.__tagFilterList != None and len(self.__tagFilterList) > 3:
                return EReaderResult.RT_NOT_FILTER_ERR
            filterParam = ""
            filterNum = 0
            for key in self.__tagFilterList:
                tagFilterModel = self.__tagFilterList[key]
                filterNum += 1
                if filterNum == 1:
                    filterParam += "1,"
                elif filterNum == 2:
                    filterParam += "13,"
                elif filterNum == 3:
                    filterParam += "14,"

                if tagFilterModel.Bank == EReadBank.EPC:
                    filterParam += Helper_String.ByteToStringOne(1)
                elif tagFilterModel.Bank == EReadBank.TID:
                    filterParam += Helper_String.ByteToStringOne(2)
                elif tagFilterModel.Bank == EReadBank.UserData:
                    filterParam += Helper_String.ByteToStringOne(3)

                filterParam += self.getHexStringByUInt16(int(tagFilterModel.tagStart))
                filterParam += Helper_String.ByteToStringOne(len(tagFilterModel.data) * 4)
                filterParam += tagFilterModel.data.strip()

                filterParam += "&"
            param += filterParam
            #endregion
            #region 循环扩展读
            extendParam = ""
            readPassWord = ""
            for key in self.__readExtendedAreaList:
                readExtendedAreaModel = self.__readExtendedAreaList[key]
                if not Helper_String.IsNullOrEmpty(readExtendedAreaModel.passWord):
                    readPassWord = readExtendedAreaModel.passWord
                if readExtendedAreaModel.bank ==EReadBank.TID:
                    extendParam += "2,"
                    extendParam += Helper_String.ByteToStringOne(int(readExtendedAreaModel.readStart))
                    extendParam += self.getHexStringByByte(int(readExtendedAreaModel.readLen))
                    extendParam += "&"
                elif readExtendedAreaModel.bank == EReadBank.UserData:
                    extendParam += "3,"
                    extendParam += self.getHexStringByUInt16(int(readExtendedAreaModel.readStart))
                    extendParam += self.getHexStringByByte(int(readExtendedAreaModel.readLen))
                    extendParam += "&"
                elif readExtendedAreaModel.bank == EReadBank.Reserved:
                    extendParam += "4,"
                    extendParam += self.getHexStringByUInt16(int(readExtendedAreaModel.readStart))
                    extendParam += self.getHexStringByByte(int(readExtendedAreaModel.readLen))
                    extendParam += "&"
                elif readExtendedAreaModel.bank == EReadBank.EpcData:
                    extendParam += "9,"
                    extendParam += self.getHexStringByUInt16(int(readExtendedAreaModel.readStart))
                    extendParam += self.getHexStringByByte(int(readExtendedAreaModel.readLen))
                    extendParam += "&"
            param += extendParam
            # endregion

            #   访问密码
            if not Helper_String.IsNullOrEmpty(readPassWord):
                param += "5," + readPassWord.strip() + "&"
            #   大于天线8
            addAntParam = self.getAddAntParam()
            PID = "10"
            if addAntParam != "0000":
                param += (PID + "," + addAntParam + "&")
            #region 循环特殊读
            specialParam = ""
            for eReadSpecial in self.__readSpecialHashSet:
                if eReadSpecial == EReadSpecial.NXP_BrandID:
                    specialParam += "17,01&"
                elif eReadSpecial == EReadSpecial.NXP_EAS_Alarm:
                    specialParam += "18,01&"
            param += specialParam
            #endregion
            param = param.rstrip('&')
            param = param.rstrip('|')
            readerStringModel.data = param
            return EReaderResult.RT_OK

        except Exception as e:
            print("方法getInventoryParam失败，错误信息%s" % e)
            return EReaderResult.RT_FAILED_ERR

    #endregion

    # 获取错误信息
    @staticmethod
    def getDetailError(rr):
        if rr == EReaderResult.RT_OK:
            return ReaderLanguage.getString("OK")
        elif rr == EReaderResult.RT_FAILED_ERR:
            return ReaderLanguage.getString("Fail")
        elif rr == EReaderResult.RT_SYSTEM_ERR:
            return ReaderLanguage.getString("SystemErr")
        elif rr == EReaderResult.RT_NOT_SUPPORTED_ERR:
            return ReaderLanguage.getString("NotSupport")
        elif rr == EReaderResult.RT_INVALID_PARA_ERR:
            return ReaderLanguage.getString("InvalidParam")
        elif rr == EReaderResult.RT_TIMEOUT_ERR:
            return ReaderLanguage.getString("ReaderTimeOut")
        elif rr == EReaderResult.RT_NOT_CONNECT_ERR:
            return ReaderLanguage.getString("NotConnect")
        elif rr == EReaderResult.RT_NOT_FILTER_ERR:
            return ReaderLanguage.getString("FilterErr")
        elif rr == EReaderResult.RT_AREA_LOCKED_ERR:
            return ReaderLanguage.getString("AreaLockedErr")
        elif rr == EReaderResult.RT_NOT_CONNECT_INFINITY_ERR:
            return ReaderLanguage.getString("NotConnectInfinityErr")
        elif rr == EReaderResult.RT_TAG_LOSS_ERR:
            return ReaderLanguage.getString("TagLossErr")
        elif rr == EReaderResult.RT_TAG_DESTORY_PASS_ERR:
            return ReaderLanguage.getString("TagDestoryPassErr")
        else:
            return ReaderLanguage.getString("NoCorrespondErrorCode")

    #   切换语言包
    @staticmethod
    def setLanguage(language):
        ReaderLanguage.language = language

    #   python打印一个对象所有属性的方法
    @staticmethod
    def print_object(obj):
        print('\n'.join(['%s:%s' % item for item in obj.__dict__.items()]))

__all__ = ['Reader']