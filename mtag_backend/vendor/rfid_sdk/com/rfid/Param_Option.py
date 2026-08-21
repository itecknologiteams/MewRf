from com.rfid.RFIDReader import RFIDReader
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.Frame_0001_00 import Frame_0001_00
from com.rfid.protocol.Frame_0001_01 import Frame_0001_01
from com.rfid.protocol.Frame_0001_02 import Frame_0001_02
from com.rfid.protocol.Frame_0001_03 import Frame_0001_03
from com.rfid.protocol.Frame_0001_04 import Frame_0001_04
from com.rfid.protocol.Frame_0001_05 import Frame_0001_05
from com.rfid.protocol.Frame_0001_06 import Frame_0001_06
from com.rfid.protocol.Frame_0001_07 import Frame_0001_07
from com.rfid.protocol.Frame_0001_08 import Frame_0001_08
from com.rfid.protocol.Frame_0001_09 import Frame_0001_09
from com.rfid.protocol.Frame_0001_0A import Frame_0001_0A
from com.rfid.protocol.Frame_0001_0B import Frame_0001_0B
from com.rfid.protocol.Frame_0001_0C import Frame_0001_0C
from com.rfid.protocol.Frame_0001_0D import Frame_0001_0D
from com.rfid.protocol.Frame_0001_0E import Frame_0001_0E
from com.rfid.protocol.Frame_0001_0F import Frame_0001_0F
from com.rfid.protocol.Frame_0001_10 import Frame_0001_10
from com.rfid.protocol.Frame_0001_11 import Frame_0001_11
from com.rfid.protocol.Frame_0001_13 import Frame_0001_13
from com.rfid.protocol.Frame_0001_14 import Frame_0001_14
from com.rfid.protocol.Frame_0001_15 import Frame_0001_15
from com.rfid.protocol.Frame_0001_16 import Frame_0001_16
from com.rfid.protocol.Frame_0001_17 import Frame_0001_17
from com.rfid.protocol.Frame_0001_18 import Frame_0001_18
from com.rfid.protocol.Frame_0001_1B import Frame_0001_1B
from com.rfid.protocol.Frame_0001_1C import Frame_0001_1C
from com.rfid.protocol.Frame_0001_1E import Frame_0001_1E
from com.rfid.protocol.Frame_0001_1F import Frame_0001_1F
from com.rfid.protocol.Frame_0001_21 import Frame_0001_21
from com.rfid.protocol.Frame_0001_23 import Frame_0001_23
from com.rfid.protocol.Frame_0001_24 import Frame_0001_24
from com.rfid.protocol.Frame_0001_2D import Frame_0001_2D
from com.rfid.protocol.Frame_0001_2E import Frame_0001_2E
from com.rfid.protocol.Frame_0001_2F import Frame_0001_2F
from com.rfid.protocol.Frame_0001_30 import Frame_0001_30
from com.rfid.protocol.Frame_0001_31 import Frame_0001_31
from com.rfid.protocol.Frame_0001_32 import Frame_0001_32
from com.rfid.protocol.Frame_0001_33 import Frame_0001_33
from com.rfid.protocol.Frame_0001_34 import Frame_0001_34
from com.rfid.protocol.Frame_0001_35 import Frame_0001_35
from com.rfid.protocol.Frame_0001_36 import Frame_0001_36
from com.rfid.protocol.Frame_0001_37 import Frame_0001_37
from com.rfid.protocol.Frame_0001_38 import Frame_0001_38
from com.rfid.protocol.Frame_0001_48 import Frame_0001_48
from com.rfid.protocol.Frame_0001_49 import Frame_0001_49
from com.rfid.protocol.Frame_0001_52 import Frame_0001_52
from com.rfid.protocol.Frame_0001_53 import Frame_0001_53
from com.rfid.protocol.Frame_0001_55 import Frame_0001_55
from com.rfid.protocol.Frame_0001_56 import Frame_0001_56
from com.rfid.protocol.Frame_0001_57 import Frame_0001_57
from com.rfid.protocol.Frame_0001_5C import Frame_0001_5C
from com.rfid.protocol.Frame_0001_5D import Frame_0001_5D
from com.rfid.protocol.Frame_0001_5E import Frame_0001_5E
from com.rfid.protocol.Frame_0001_5F import Frame_0001_5F
from com.rfid.protocol.Frame_0001_60 import Frame_0001_60
from com.rfid.protocol.Frame_0001_61 import Frame_0001_61
from com.rfid.protocol.Frame_0001_62 import Frame_0001_62
from com.rfid.protocol.Frame_0001_63 import Frame_0001_63
from com.rfid.protocol.Frame_0001_64 import Frame_0001_64
from com.rfid.protocol.Frame_0001_65 import Frame_0001_65
from com.rfid.protocol.Frame_0001_66 import Frame_0001_66
from com.rfid.protocol.Frame_0001_F0 import Frame_0001_F0
from com.rfid.protocol.Frame_0010_56 import Frame_0010_56
from com.rfid.protocol.Frame_0100_00 import Frame_0100_00
from com.rfid.protocol.Frame_0100_01 import Frame_0100_01
from com.rfid.protocol.Frame_0101_33 import Frame_0101_33

#   Reader操作类
class Param_Option:
    S_TIMEOUT = "-2|Timeout!"
    S_EXCPTION = "-3|Parameters error!"

    def __init__(self):
        pass

    @staticmethod
    def ChangeLanguage(typeCode):
        if typeCode == 0:
            S_TIMEOUT = "-2|通信超时!"
            S_EXCPTION = "-3|参数错误!"
        else:
            S_TIMEOUT = "-2|Timeout!"
            S_EXCPTION = "-3|Parameters error!"

    # 重启读写器
    # param connID 连接标识
    @staticmethod
    def ReSetReader(connID):
        try:
            bf = Frame_0001_0F()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
        except Exception as e:
            # print("失败，解包失败:%s" % e)
            pass

    # 获得读写器信息
    # param connID 连接标识
    # return 应用处理器软件版本|读写器名称|读写器上电时间
    @staticmethod
    def GetReaderInformation(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_00()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_00)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    # 获得读写器基带软件版本
    # param connID 连接标识
    # return V1.0.0
    @staticmethod
    def GetReaderBasebandSoftVersion(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_01()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_01)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    # 获得基带序列号
    # return 5100HH0020060001
    @staticmethod
    def GetReaderBasebandSerialNo(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0101_33()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0101_33)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
                if not rt.startswith("-"):
                    RFIDReader.HP_CONNECT[connID]._ReaderSN = rt
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    # 配置串口参数
    # connID 连接标识
    # param 0，9600 bps|1，19200 bps|2，115200 bps|3，230400 bps|4，460800bps
    @staticmethod
    def SetReaderSerialPortParam(connID,param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_02(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_02)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    # 查询串口参数
    # param connID 连接标识
    #  return 0，9600 bps1/19200 bps/2，115200 bps/3，230400 bps/4,460800bps/其他，不支持/读写器--默认为115200 bps。
    @staticmethod
    def GetReaderSerialPortParam(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_03()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_03,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    # 配置网口参数
    # @param connID 连接标识
    # @param param 192.168.1.8|255.255.255.0|192.168.1.1
    @staticmethod
    def SetReaderNetworkPortParam(connID,param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_04(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_04,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as ex:
            rt = Param_Option.S_EXCPTION
        return rt

    # 查询网口参数
    # @param connID 连接标识
    # @return 192.168.1.8|255.255.255.0|192.168.1.1
    @staticmethod
    def GetReaderNetworkPortParam(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_05()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_05)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    # 设置读写器MAC地址
    # @param connID 连接标识
    # @param param 00-00-00-00-00-00
    @staticmethod
    def SetReaderMacParam(connID,param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_13(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_13,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    # 读取读写器MAC地址
    # @param connID 连接标识
    # @return 00-00-00-00-00-00
    @staticmethod
    def GetReaderMacParam(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_06()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_06,5000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    # 配置服务器/客户端模式参数
    # @param connID 连接标识
    # @param param 0 或者 0|1,9090 或者 1|2,192.168.1.1 & 3,9090
    @staticmethod
    def SetReaderServerOrClient(connID,param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_07(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_07,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    查询服务器/客户端模式参数
    # 	 @param connID 连接标识
    # 	 @return 0|9090|192.168.1.1|9090
    @staticmethod
    def GetReaderServerOrClient(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_08()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_08)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    配置GPO状态
    # 	 @param connID 连接标识
    # 	 @param param 1,0 & 2,0 & 3,0 & 4,0
    @staticmethod
    def SetReaderGPOState(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_09(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_09)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    查询GPI状态
    # 	 @return 1,0 & 2,0 & 3,0 & 4,0
    @staticmethod
    def GetReaderGPIState(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_0A()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_0A)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    # 	 配置GPI触发参数
    # 	 @param connID 连接标识
    # 	 @param param 0|0|触发指令|0|1,u16
    @staticmethod
    def SetReaderGPIParam(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_0B(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_0B)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    查询GPI触发参数
    # 	 @param connID 连接标识
    # 	 @param param GPI端口号
    # 	 @return 0|0|触发绑定的指令|0|U16
    @staticmethod
    def GetReaderGPIParam(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_0C(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_0C)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    配置韦根通信参数
    # 	 @param connID 连接标识
    # 	 @param param 韦根通信开关|韦根通信格式|韦根传输数据内容
    @staticmethod
    def SetReaderWG(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_0D(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_0D)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    查询韦根通信参数
    # 	 @param connID 连接标识
    # 	 @return 韦根通信开关|韦根通信格式|韦根传输数据内容
    @staticmethod
    def GetReaderWG(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_0E()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_0E)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   设置读写器时间
    # 	 @param connID 连接标识
    # 	 @param param 0000.0000
    @staticmethod
    def SetReaderUTC(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_10(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_10)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   读取读写器时间
    # 	 @param connID 连接标识
    # 	 @return 0000.0000
    @staticmethod
    def GetReaderUTC(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_11()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_11)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   恢复读写器默认配置
    # 	 @param connID 连接标识
    # 	 @param param 5AA5A55A
    @staticmethod
    def SetReaderRestoreFactory(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_14(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_14,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   配置读写器RS485设备地址
    # 	 @param connID 连接标识
    # 	 @param param 0-255|1,1
    @staticmethod
    def SetReader485(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_15(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_15,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询读写器RS485设备地址
    # 	 @param connID 连接标识
    # 	 @return 0-255|1
    @staticmethod
    def GetReader485(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_16()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_16)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   配置读写器断点续传
    # 	 @param connID 连接标识
    # 	 @param param 0关闭，1启用
    @staticmethod
    def SetBreakPointUpload(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_17(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_17)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询读写器断点续传
    # 	 @param connID 连接标识
    # 	 @return 0关闭，1启用
    @staticmethod
    def GetBreakPointUpload(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_18()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_18)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询读写器断点续传标签缓存
    # 	 @param connID 连接标识
    # 	 @return 0有缓存，1无缓存，2数据返回结束
    @staticmethod
    def GetBreakPointCacheTag(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_1B()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_1B)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   清除断点续传缓存
    # 	 @param connID 连接标识
    # 	 @return 0清除成功，1清除失败
    @staticmethod
    def ClearBreakPointCache(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_1C()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_1C)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   region 升级指令
    #   更新应用软件,一包数据
    # 	 @param connID 连接标识
    # 	 @param dataIndex 升级数据编号0x00000000 开始，0xFFFFFFFF 结束。
    # 	 @param param 升级数据内容
    @staticmethod
    def UpdateApplication(connID, dataIndex,param):
        rt = ""
        try:
            bf = Frame_0100_00(dataIndex, param)
            for i in range(0,3):
                RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
                rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0100_00)
                if rtFrame != None:
                    rt = rtFrame.GetReturnData(rtFrame)
                if not Helper_String.IsNullOrEmpty(rt):
                    break
        except Exception as e:
            rt = ""
        return rt

    #   更新基带软件,一包数据
    # 	 @param connID 连接标识
    # 	 @param dataIndex 升级数据编号0x00000000 开始，0xFFFFFFFF 结束。
    # 	 @param param 升级数据内容
    @staticmethod
    def UpdateBaseband(connID, dataIndex, param):
        rt = ""
        try:
            bf = Frame_0100_01(dataIndex, param)
            for i in range(0, 3):
                RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
                rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0100_01,3000)
                if rtFrame != None:
                    rt = rtFrame.GetReturnData(rtFrame)
                if not Helper_String.IsNullOrEmpty(rt):
                    break
        except Exception as e:
            rt = ""
        return rt
    # endregion

    #    配置DHCP
    # 	 @param connID 连接标识
    # 	 @param DHCP开关，0为关闭，1为打开
    # 	 @return 0为配置成功，1为配置失败
    @staticmethod
    def SetDHCP(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_2F(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_2F,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    查询DHCP
    # 	 @param connID 连接标识
    # 	 @return 0为DHCP关闭，1为DHCP打开
    @staticmethod
    def GetDHCP(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_30()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_30)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    设置读写器网络自检功能
    # 	 @param connID 连接标识
    #    @param 检测开关|检测ip地址
    # 	 @return 0设置成功，1设置失败
    @staticmethod
    def SetReaderSelfCheck(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_2D(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_2D)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    查询读写器网络自检功能
    # 	 @param connID 连接标识
    # 	 @return 检测开关|检测ip地址
    @staticmethod
    def GetReaderSelfCheck(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_2E()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_2E)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    搜索WIFI热点
    # 	 @param connID 连接标识
    # 	 @return 0为OK，1为硬件不支持
    @staticmethod
    def SearchWIFI(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_31()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_31,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #    请求Wifi搜索结果数据包
    @staticmethod
    def RequestWiFiInfo(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_32(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_32)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   连接WIFI热点
    # 	 @param connID 连接标识
    # 	 @return 0为OK，1为失败
    @staticmethod
    def ConnectWIFI(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_33(param)
            for i in range(0,3):
                RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
                rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_33)
                if rtFrame != None:
                    rt = rtFrame.GetReturnData(rtFrame)
                if Helper_String.IsNullOrEmpty(rt):
                    break
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询WIFI连接信息
    @staticmethod
    def GetWifiConnectInfo(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_34()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_34)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   配置Wifi网卡IP
    # 	@param connID 连接标识
    # 	@return 192.168.1.8|255.255.255.0|192.168.1.1
    @staticmethod
    def SetReaderWifiIP(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_35(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_35, 3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询Wifi网卡IP
    # 	@param connID 连接标识
    # 	@return 192.168.1.8|255.255.255.0|192.168.1.1
    @staticmethod
    def GetReaderWifiIP(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_36()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_36)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   配置读写器WiFi网卡开关
    @staticmethod
    def SetWiFiSwitch(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_37(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_37, 3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询WiFi开关状态
    @staticmethod
    def GetWiFiSwitchState(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_38()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_38)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   设置蜂鸣器开关
    #   param 开关 0：读写器控制，1：上位机控制
    @staticmethod
    def SetBuzzerSwitch(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_1E(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_1E)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询蜂鸣器开关
    #   return 开关 0：读写器控制,1：上位机控制
    @staticmethod
    def GetBuzzerSwitch(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_55()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_55)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   配置状态指示灯
    #   connID  连接标识
    #   param 0 或者 0|1,20
    @staticmethod
    def SetReaderStateLED(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_65(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_65)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询状态指示灯
    #   connID  连接标识
    #   return 0 或者 0|1,20
    @staticmethod
    def GetReaderStateLED(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_66()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_66)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   设置蜂鸣器控制
    #   connID  连接标识
    #   param eg:0001 ==> byte0: 00：蜂鸣器停止/01：响  byte1：00: 蜂鸣器响一次/01:常响  <
    @staticmethod
    def SetBuzzerControl(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_1F(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_1F)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   下发白名单数据
    #   param connID 连接标识
    #   param dataIndex 升级数据编号0x00000000 开始，0xFFFFFFFF 结束。
    #   param param 白名单数据
    @staticmethod
    def LoadWhiteList(connID,dataIndex, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_21(dataIndex, param)
            for i in range(0,3):
                RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
                rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_21,3000)
                if rtFrame != None:
                    rt = rtFrame.GetReturnData(rtFrame)
                if not Helper_String.IsNullOrEmpty(rt):
                    break
        except Exception as e:
            rt = ""
        return rt

    #   配置白名单动作参数
    #   param   继电器号|蜂鸣器闭合/鸣叫时间|输出功能开关|白名单功能数据类型
    @staticmethod
    def SetWhitelistLabelAction(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_23(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_23)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   获取白名单动作参数
    #   connID  连接标识
    @staticmethod
    def GetWhitelistLabelAction(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_24()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_24)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   心跳包检测设置
    #   connID  连接标识
    #   param   心跳包发送间隔|心跳包检测次数
    @staticmethod
    def SetHeartbeat(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_48(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_48)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   获取心跳设置
    #   connID  连接标识
    @staticmethod
    def GetHeartbeat(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_49()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_49)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   获取读写器电量
    #   connID  连接标识
    @staticmethod
    def GetReaderElectricity(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_52()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_52)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   启动扫描头
    #   connID  连接标识
    @staticmethod
    def SetScanHead(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_53()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_53)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   启动扫描头
    #   connID  连接标识
    #   param   特殊格式输出开关|数据输出格式|输出数据类型|数据帧头|保留|保留|数据帧尾
    @staticmethod
    def SetDataOutputFormat(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_56(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_56)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   获取数据输出格式
    #   connID  连接标识
    @staticmethod
    def GetDataOutputFormat(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_57()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_57)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询国标时钟同步参数
    #   connID  连接标识
    #   return  255|255
    @staticmethod
    def GetGBGardner(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0010_56()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_56)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   获取UDP参数
    #   return  9090|192.168.1.100
    @staticmethod
    def GetUDPParams(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_5D()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_5D)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   设置UDP参数
    #   9090|192.168.1.100
    @staticmethod
    def SetUDPParams(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_5C(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_5C,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   获取自定义编码
    @staticmethod
    def GetCustomCode(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_5E()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_5E)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   设置自定义编码
    #   0A0B|0A0A0A0A
    @staticmethod
    def SetCustomCode(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_5F(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_5F)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   获取读写器温度
    @staticmethod
    def GetReaderTemperature(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_60()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_60)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   配置默认连接
    #   0A0B|0A0A0A0A
    @staticmethod
    def SetReaderDefaultConnType(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_62(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_62)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   查询串口参数
    #   param   0，RS232|1，RS485|2，TCP|3，USB
    @staticmethod
    def GetReaderDefaultConnType(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_61()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_61)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   设置读写器NTP
    #   param   开关|ip地址/主机名称
    #   return   0设置成功，1设置失败
    @staticmethod
    def SetReaderNTP(connID, param):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_64(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_64)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    #   设置读写器NTP
    #   return   开关|ip地址/主机名称
    @staticmethod
    def GetReaderNTP(connID):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_63()
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_63)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt

    @staticmethod
    def readerXfer(connID,param, timout):
        rt = Param_Option.S_TIMEOUT
        try:
            bf = Frame_0001_F0(param)
            RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0001_F0,timout)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = Param_Option.S_EXCPTION
        return rt
