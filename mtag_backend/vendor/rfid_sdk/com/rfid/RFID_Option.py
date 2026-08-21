from com.rfid import RFIDReader
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.Frame_0010_00 import Frame_0010_00
from com.rfid.protocol.Frame_0010_01 import Frame_0010_01
from com.rfid.protocol.Frame_0010_02 import Frame_0010_02
from com.rfid.protocol.Frame_0010_03 import Frame_0010_03
from com.rfid.protocol.Frame_0010_04 import Frame_0010_04
from com.rfid.protocol.Frame_0010_05 import Frame_0010_05
from com.rfid.protocol.Frame_0010_06 import Frame_0010_06
from com.rfid.protocol.Frame_0010_07 import Frame_0010_07
from com.rfid.protocol.Frame_0010_08 import Frame_0010_08
from com.rfid.protocol.Frame_0010_09 import Frame_0010_09
from com.rfid.protocol.Frame_0010_0A import Frame_0010_0A
from com.rfid.protocol.Frame_0010_0B import Frame_0010_0B
from com.rfid.protocol.Frame_0010_0C import Frame_0010_0C
from com.rfid.protocol.Frame_0010_0D import Frame_0010_0D
from com.rfid.protocol.Frame_0010_0E import Frame_0010_0E
from com.rfid.protocol.Frame_0010_10 import Frame_0010_10
from com.rfid.protocol.Frame_0010_11 import Frame_0010_11
from com.rfid.protocol.Frame_0010_12 import Frame_0010_12
from com.rfid.protocol.Frame_0010_13 import Frame_0010_13
from com.rfid.protocol.Frame_0010_20 import Frame_0010_20
from com.rfid.protocol.Frame_0010_30 import Frame_0010_30
from com.rfid.protocol.Frame_0010_40 import Frame_0010_40
from com.rfid.protocol.Frame_0010_41 import Frame_0010_41
from com.rfid.protocol.Frame_0010_42 import Frame_0010_42
from com.rfid.protocol.Frame_0010_43 import Frame_0010_43
from com.rfid.protocol.Frame_0010_50 import Frame_0010_50
from com.rfid.protocol.Frame_0010_51 import Frame_0010_51
from com.rfid.protocol.Frame_0010_52 import Frame_0010_52
from com.rfid.protocol.Frame_0010_53 import Frame_0010_53
from com.rfid.protocol.Frame_0010_E0 import Frame_0010_E0
from com.rfid.protocol.Frame_0010_E1 import Frame_0010_E1
from com.rfid.protocol.Frame_0010_E2 import Frame_0010_E2
from com.rfid.protocol.Frame_0010_E3 import Frame_0010_E3
from com.rfid.protocol.Frame_0010_FF import Frame_0010_FF
from com.rfid.protocol.Frame_0101_00 import Frame_0101_00
from com.rfid.protocol.Frame_0101_05 import Frame_0101_05


class RFID_Option:
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

    #   获得读写器的读写能力
    #   @param connID 连接标识
    # 	 @return 最小发射功率|最大发射功率|天线数目|频段列表|RFID协议列表
    @staticmethod
    def GetReaderProperty(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_00()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_00)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   停止指令
    #   @param connID 连接标识
    # 	 @return 是否成功
    @staticmethod
    def StopReader(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_FF()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_FF)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   设置天线功率
    # 	 @param connID 连接标识
    # 	 @param param "1,21&2,21&3,21&4,21"		一直到24天线
    @staticmethod
    def SetReaderPower(connID,param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_01(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_01)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   查询天线功率
    #
    # 	 @param connID 连接标识
    # 	 @return 查询结果
    @staticmethod
    def GetReaderPower(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_02()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_02)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   设置RF频段
    #
    # 	 @param connID 连接标识
    # 	 @param param "0，国标920~925MHz 1，国标840~845MHz 2，国标840~845MHz和920~925MHz 3，FCC，902~928MHz 4,ETSI，866~868MHz"
    @staticmethod
    def SetReaderRF(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_03(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_03)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   查询RF频段
    #
    # 	 @param connID 连接标识
    # 	 @return 查询结果
    @staticmethod
    def GetReaderRF(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_04()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_04)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   配置EPC基带参数
    #
    # 	 @param connID 连接标识
    # 	 @param param 1,0~255 & 2,0~255 & 3,0~255 & 4,0~255
    @staticmethod
    def SetEPCBasebandParam(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_0B(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_0B)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt


    #   查询EPC基带参数
    #
    # 	 @param connID 连接标识
    # 	 @return 0~255|0~255|0~255|0~255
    # 	 * @throws InterruptedException
    @staticmethod
    def GetEPCBasebandParam(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_0C()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_0C)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   配置读写器功率
    #
    # 	 @param connID 连接标识
    # 	 @param param 1,21&2,21&3,21&4,21
    @staticmethod
    def SetANTPowerParam(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_01(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_01)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   查询读写器功率
    #
    # 	 @param connID 连接标识
    # 	 @return 1,21&2,21&3,21&4,21
    @staticmethod
    def GetANTPowerParam(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_02()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_02)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   配置读写器工作频率
    #
    # 	 @param connID 连接标识
    # 	 @param param 0~255|0,7,15
    @staticmethod
    def SetReaderWorkFrequency(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_05(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_05)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   查询读写器工作频率
    #
    # 	 @param connID 连接标识
    # 	 @return 1:21&2:21&3:21&4:21
    def GetReaderWorkFrequency(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_06()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_06)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   配置读写器天线
    #
    # 	 @param connID 连接标识
    # 	 @param param 0~255|1,1-2-3-5-7&2,4-5-6
    @staticmethod
    def SetReaderANT(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_07(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_07)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   查询读写器天线
    #
    # 	 @param connID 连接标识
    # 	 @return 0~255
    @staticmethod
    def GetReaderANT(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_08()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_08)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   配置标签上传参数
    #
    # 	 @param connID 连接标识
    # 	 @param param 1,0~65535 & 2,0~255
    @staticmethod
    def SetTagUpdateParam(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_09(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_09)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   查询标签上传参数
    #
    # 	 @param connID 连接标识
    # 	 @return 0~65535 | 0~255
    @staticmethod
    def GetTagUpdateParam(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_0A()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_0A)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   配置读写器自动空闲模式
    #
    # 	 @param connID 连接标识
    # 	 @param param 0~255 | 1,0~65535
    @staticmethod
    def SetReaderAutoSleepParam(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_0D(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_0D)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   查询读写器自动空闲模式
    #
    # 	 @param connID 连接标识
    # 	 @return 0~255 | 1,0~65535
    @staticmethod
    def GetReaderAutoSleepParam(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_0E()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_0E)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   读EPC标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|连续/单次读取|1,读取参数 & 2,TID读取参数 & 3,用户数据区读取参数 & 4,保留区读取参数 & 5,标签访问密码
    @staticmethod
    def GetEPC(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_10(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_10)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   读 6C & 6B 标签
    #
    # 	 @param connID 连接标识
    # 	 @param param6C
    # 	 @param param6B
    @staticmethod
    def Get6C_6B(connID, param6C,param6B):
        rt = RFID_Option.S_TIMEOUT
        try:
            RFIDReader.RFIDReader.HP_CONNECT[connID].Is6B_6C_Start = True
            RFID_Option.StartRead6B_6C(connID, param6C, param6B)
            rt = "0|OK!"
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   停止读 6B & 6C
    #
    # 	 @param connID
    @staticmethod
    def STOP_6C_6B(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            RFIDReader.RFIDReader.HP_CONNECT[connID].Is6B_6C_Start = False
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   获得读EPC指令内容(用于配置GPI)
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|连续/单次读取|1,读取参数 & 2,TID读取参数 & 3,用户数据区读取参数 & 4,保留区读取参数 & 5,标签访问密码
    # 	 @return 空字符串或指令内容
    @staticmethod
    def GetEPC_Command(connID,param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_10(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rt = Helper_String.ByteToString(bf.GetFreamData(False))
            if len(rt) > 3:
                rt = rt[2: 2 + len(rt) - 6]
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   写EPC
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|数据区|字起始地址|数据内容|0x01,选择写入参数 & 0x02,标签访问密码 & 块写参数
    @staticmethod
    def WriteEPC(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_11(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_11,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   锁EPC
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|锁操作区域|锁操作类型|0x01,选择写入参数 & 0x02,标签访问密码
    @staticmethod
    def LockEPC(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_12(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_12,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   读6B标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|连续/单次读取|读取内容(0-1-2)|1,用户数据读取参数 & 2,待匹配的TID
    @staticmethod
    def Get6B(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_40(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_40)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   获得读6B标签指令内容(用于配置GPI)
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|连续/单次读取|读取内容(0-1-2)|1,用户数据读取参数 & 2,待匹配的TID
    # 	 @return 空字符串或指令内容
    @staticmethod
    def Get6B_Command(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_40(param)
            rt = Helper_String.ByteToString(bf.GetFreamData(False))
            if len(rt) > 3:
                rt = rt[2: 2 + len(rt)- 6]
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   写6B标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|待写标签的TID|起始地址|数据内容
    @staticmethod
    def Write6B(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_41(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_41, 3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   锁6B标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|待锁定标签TID|锁定地址
    @staticmethod
    def Lock6B(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_42(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_42, 3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   6B标签锁定查询
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|待锁定标签TID|锁定地址
    @staticmethod
    def GetLock6B(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_43(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_43)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   销毁EPC
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|灭活密码|0x01,选择写入参数 & 0x02,标签访问密码
    @staticmethod
    def DestroyEPC(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_13(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_13,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   读取国标标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|连续/单次读取|1,读取参数 & 2,TID读取参数 & 3,用户数据区读取参数 & 5,标签访问密码
    @staticmethod
    def GetGB(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_50(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_50)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   写国标标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|数据区|字起始地址|数据内容|0x01,选择写入参数 & 0x02,标签访问密码
    @staticmethod
    def WriteGB(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_51(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_51,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   锁国标标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|锁操作区域|锁参数|0x01,选择锁定参数 & 0x02,标签访问密码
    @staticmethod
    def LockGB(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_52(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_52,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   销毁国标标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口||0x01,选择灭活参数 & 0x02,标签灭活密码
    @staticmethod
    def DestroyGB(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_53(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_53,3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   G2V2 Untraceable操作
    @staticmethod
    def G2V2UntraceableOption(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_20(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_20, 3000)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   发射载波
    @staticmethod
    def SendCarrier(connID,param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0101_00(param)
            RFIDReader.RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0101_00)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   R2000直流偏置校准
    @staticmethod
    def Set_0101_01(connID,param):
        pass

    #   R2000直流偏置校准查询
    @staticmethod
    def Get_0101_02(connID,param):
        pass

    #   读写器功率校准
    @staticmethod
    def Set_0101_03(connID,param):
        pass

    #   读写器功率校准参数查询
    @staticmethod
    def Set_0101_04(connID,param):
        pass

    #   读写器天线端口驻波检测
    @staticmethod
    def Get_0101_05(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0101_05()
            RFIDReader.RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0101_05)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   pr9200外部PA反馈参数
    @staticmethod
    def Set_0101_06(connID,param):
        pass

    #   读写器天线端口驻波检测
    @staticmethod
    def Get_0101_07(connID,param):
        pass

    #   开启线程循环读6B加6C标签
    @staticmethod
    def StartRead6B_6C(connID, param6C, param6B):
        pass

    #   	 查询RFID温度
    #
    # 	 @param connID 连接标识
    # 	 @return RFID温度
    @staticmethod
    def GetRFIDTemperature(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_30()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_30)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   配置EPC扩展基带参数
    #
    # 	 @param connID 参数
    # 	 @return 设置结果
    @staticmethod
    def SetEPCBaseExpandBandParam(connID,param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_E0(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_E0)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   配置EPC扩展基带参数
    #
    # 	 @param connID 参数
    # 	 @return 设置结果
    @staticmethod
    def GetEPCBaseExpandBandParam(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_E1()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_E1)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   查询可选上报参数
    #   1,0 & 2,0 & 3,0 & 4,0
    @staticmethod
    def GetOptionReportParam(connID):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_E3()
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_E3)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt

    #   配置可选上报参数
    #   1,0 & 2,0 & 3,0 & 4,0
    @staticmethod
    def SetOptionReportParam(connID, param):
        rt = RFID_Option.S_TIMEOUT
        try:
            bf = Frame_0010_E2(param)
            RFIDReader.RFIDReader.HP_CONNECT[connID].SendSingleFrame(bf)
            rtFrame = RFIDReader.RFIDReader.HP_CONNECT[connID].WaitResponse(Frame_0010_E2)
            if rtFrame != None:
                rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = RFID_Option.S_EXCPTION
        return rt



