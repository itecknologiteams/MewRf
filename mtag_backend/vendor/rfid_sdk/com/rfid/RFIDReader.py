import usb

from com.rfid import Param_Option
from com.rfid.RFID_Option import RFID_Option
from com.rfid.ReaderConfig import ReaderConfig
from com.rfid.Tag6C import Tag6C
from com.rfid.connect import *
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.Frame_0001_09 import Frame_0001_09
from com.rfid.protocol.Frame_0010_00 import Frame_0010_00
from com.rfid.protocol.Frame_0010_01 import Frame_0010_01
from com.rfid.protocol.Frame_0010_02 import Frame_0010_02
from com.rfid.protocol.Frame_0010_03 import Frame_0010_03
from com.rfid.protocol.Frame_0010_04 import Frame_0010_04
from com.rfid.protocol.Frame_0010_09 import Frame_0010_09
from com.rfid.protocol.Frame_0010_0B import Frame_0010_0B
from com.rfid.protocol.Frame_0010_0C import Frame_0010_0C
from com.rfid.protocol.Frame_0010_10 import Frame_0010_10
from com.rfid.protocol.Frame_0010_11 import Frame_0010_11
from com.rfid.protocol.Frame_0010_12 import Frame_0010_12
from com.rfid.protocol.Frame_0010_13 import Frame_0010_13
from com.rfid.protocol.Frame_0010_14 import Frame_0010_14
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
from com.rfid.protocol.Frame_0010_FF import Frame_0010_FF
from com.rfid.protocol.Frame_0100_01 import Frame_0100_01
from com.rfid.protocol.Frame_0101_00 import Frame_0101_00
from com.rfid.protocol.Frame_0101_05 import Frame_0101_05
import hid


class RFIDReader:

    VERSION_STRING = "2.11"
    #   服务器监听对象
    LISTENER = None
    #   关闭服务器监听的时候，是否关闭其已经连接的子连接
    ISCLOSE_LISTENER_CHILD_CONNECT = True
    #   换成Windows 平台路径
    # _UpdateFilePath = "/data/app/R2000_D2_4S4B.bin"
    _GetError = "Failed to get!"
    #   存放所有的上下文连接
    HP_CONNECT = {}
    MAX_CONNCET_COUNT = 200
    _Tag6C = Tag6C()
    _Tag6B = None
    _TagGB = None
    _Config = ReaderConfig()
    _DeviceSearch = None
    listUsbDevice = []

    #   创建TCP连接
    # 	 * @param tcpParam 连接参数192.168.1.1:9090
    # 	 * @param log 调试信息输出接口
    # 	 * @return 连接是否成功
    @staticmethod
    def CreateTcpConn(tcpParam,log):
        try:
            if (not tcpParam in RFIDReader.HP_CONNECT) and len(RFIDReader.HP_CONNECT) <= RFIDReader.MAX_CONNCET_COUNT:
                address = tcpParam.find(":")
                ip = tcpParam[0: address]
                port = tcpParam[address + 1: len(tcpParam)]
                bc = TcpConnect(ip, int(port))
                bc.myLog = log
                if bc.OpenConnect():
                    RFIDReader.HP_CONNECT[tcpParam] = bc
                    if not RFIDReader.CheckConnect(tcpParam):
                        RFIDReader.CloseConn(tcpParam)
                        return False
                else:
                    return False
                return True
        except Exception as e:
            print(str(e))
        return False

    #    创建串口连接
    # 	 * @param serialParam 串口连接参数, 如：COM1:115200
    # 	 * @param log log 信息输出接口
    # 	 * @return 连接是否成功
    @staticmethod
    def CreateSerialConn(serialParam, log):
        try:
            if (not serialParam in RFIDReader.HP_CONNECT) and len(RFIDReader.HP_CONNECT) <= RFIDReader.MAX_CONNCET_COUNT:
                params = serialParam.rstrip(":").split(":")
                bc = SerialConnect(params[0], int(params[1]))
                bc.myLog = log
                if bc.OpenConnect():
                    RFIDReader.HP_CONNECT[serialParam] = bc
                    if not RFIDReader.CheckConnect(serialParam):
                        RFIDReader.CloseConn(serialParam)
                        return False
                else:
                    return False
            return True
        except Exception as e:
            pass
        return False

    #    创建485连接
    # 	 * @param _485Param 485连接参数，如：1:COM1:115200
    # 	 * @param log 信息输出接口
    # 	 * @return 连接是否成功
    @staticmethod
    def Create485Conn(_485Param, log):
        try:
            if (not _485Param in RFIDReader.HP_CONNECT) and len(RFIDReader.HP_CONNECT) <= RFIDReader.MAX_CONNCET_COUNT:
                params = _485Param.rstrip(":").split(":")
                bc = SerialConnect(params[1], int(params[2]))
                bc.myLog = log
                bc._Is485 = True
                if int(params[0]) > 127: # 解决128 - 255转换成byte变成负数的问题
                    bc._485Mac = int(params[0]) - 256
                else:
                    bc._485Mac = int(params[0])
                if bc.OpenConnect():
                    RFIDReader.HP_CONNECT[_485Param] = bc
                    if not RFIDReader.CheckConnect(_485Param):
                        RFIDReader.CloseConn(_485Param)
                        return False
                else:
                    return False
            return True
        except Exception as e:
            pass
        return False

    @staticmethod
    def CreateUsbConn(usbDevice, log):
        try:
            if (not usbDevice in RFIDReader.HP_CONNECT) and len(RFIDReader.HP_CONNECT) <= RFIDReader.MAX_CONNCET_COUNT:
                bc = None
                if usbDevice.__contains__("1a86") and usbDevice.__contains__("e429"):
                    #   bc = CH9329HidConnect(usbDevice)
                    pass
                else:
                    bc = UsbConnect(usbDevice)
                bc.myLog = log

                if bc.OpenConnect():
                    RFIDReader.HP_CONNECT[usbDevice] = bc
                    if not RFIDReader.CheckConnect(usbDevice):
                        RFIDReader.CloseConn(usbDevice)
                        return False
                else:
                    return False
            return True
        except Exception as e:
            pass
        return False

    #   获取USB设备列表
    # 	 厂商号:0x2121  产品号:0x8633
    @staticmethod
    def GetUsbHidDeviceList():
        try:
            RFIDReader.listUsbDevice.clear()
            lst = []
            for device_dict in hid.enumerate():
                if (device_dict['vendor_id'] == 0x2121 and device_dict['product_id'] == 0x8633) or(device_dict['vendor_id'] == 0x1a86 and device_dict['product_id'] == 0xe429) or(device_dict['vendor_id'] == 0x0e8d and device_dict['product_id'] == 0x201d):
                    deviceDes = 'Bus ' + str(device_dict['release_number']).rjust(3, '0') + ': ID ' + "{:x}".format(device_dict['vendor_id']) + ':' + "{:x}".format(device_dict['product_id'])
                    RFIDReader.listUsbDevice.append(deviceDes)
                    lst.append(str(deviceDes))
            return lst
        except Exception as e:
            return None

    @staticmethod
    def setAsynchronousMessage(ConnectID,log):
        with RFIDReader.HP_CONNECT:
            try:
                if RFIDReader.HP_CONNECT.get(ConnectID) != None:
                    RFIDReader.HP_CONNECT[ConnectID].myLog = log
                    return True
            except Exception as e:
                pass
        return False

    @staticmethod
    def CheckConnect(ConnectID):
        result = False
        for i in range(0,3):
            try:
                if Param_Option.Param_Option.GetReaderBasebandSoftVersion(ConnectID).startswith("V"):
                    result = True
                    break
            except Exception as e:
                pass
        return result

    #   关闭单个连接
    @staticmethod
    def CloseConn(ConnectID):
        try:
            if RFIDReader.HP_CONNECT.get(ConnectID) != None:
                RFIDReader.HP_CONNECT.get(ConnectID).CloseConnect()
                RFIDReader.HP_CONNECT.pop(ConnectID)
        except Exception as e:
            print("CloseConn() 发生异常：%s" % e)

    #   关闭所有连接
    @staticmethod
    def CloseAllConnect():
        try:
            for item in RFIDReader.HP_CONNECT:
                RFIDReader.HP_CONNECT.get(item).CloseConnect()
        except Exception as e:
            print("CloseConn() 发生异常：%s" % e)

    #   停止指令
    @staticmethod
    def Stop(connID):
        rt = ""
        getStatus = Frame_0010_FF()
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_FF)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   读EPC
    # 	 * @param param 天线端口|连续/单次读取|1,读取参数 & 2,TID读取参数 & 3,用户数据区读取参数 & 4,保留区读取参数 & 5,标签访问密码
    @staticmethod
    def Read_EPC(connID,param):
        rt = ""
        getStatus = Frame_0010_10(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_10)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   写EPC
    # 	 * @param param 天线端口|数据区|字起始地址|数据内容|0x01,选择写入参数 & 0x02,标签访问密码 & 块写参数
    @staticmethod
    def WriteEPC(connID, param):
        rt = ""
        getStatus = Frame_0010_11(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_11,3000)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   锁6C标签
    # 	 * @param connID 连接标识
    # 	 * @param param 天线端口|锁操作区域|锁操作类型|0x01,选择写入参数 & 0x02,标签访问密码
    @staticmethod
    def LockEPC(connID, param):
        rt = ""
        getStatus = Frame_0010_12(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_12,3000)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   灭活标签
    # 	 * @param param 天线端口|灭活密码|0x01,选择写入参数
    @staticmethod
    def DestroyEPC(connID, param):
        rt = ""
        getStatus = Frame_0010_13(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_13, 3000)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   读6B标签
    # 	 * @param param 天线端口|连续/单次读取|读取内容(0-1-2)|1,用户数据读取参数 & 2,待匹配的TID
    @staticmethod
    def Get6B(connID, param):
        rt = ""
        getStatus = Frame_0010_40(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_40)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   写6B标签
    # 	 * @param param 天线端口|待写标签的TID|起始地址|数据内容
    @staticmethod
    def Write6B(connID, param):
        rt = ""
        getStatus = Frame_0010_41(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_41,3000)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   锁6B标签
    # 	 * @param param 天线端口|待锁定标签TID|锁定地址
    @staticmethod
    def Lock6B(connID, param):
        rt = ""
        getStatus = Frame_0010_42(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_42,3000)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   锁6B标签查询
    # 	 * @param param 天线端口|待锁定标签TID|锁定地址
    @staticmethod
    def GetLock6B(connID, param):
        rt = ""
        getStatus = Frame_0010_43(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_43)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   读取国标标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|连续/单次读取|1,读取参数 & 2,TID读取参数 & 3,用户数据区读取参数 & 5,标签访问密码
    @staticmethod
    def GetGB(connID, param):
        rt = ""
        getStatus = Frame_0010_50(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_50)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   写国标标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|数据区|字起始地址|数据内容|0x01,选择写入参数 & 0x02,标签访问密码
    @staticmethod
    def WriteGB(connID, param):
        rt = ""
        getStatus = Frame_0010_51(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_51,3000)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   锁国标标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口|锁操作区域|锁参数|0x01,选择锁定参数 & 0x02,标签访问密码
    @staticmethod
    def LockGB(connID, param):
        rt = ""
        getStatus = Frame_0010_52(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_52,3000)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   销毁国标标签
    #
    # 	 @param connID 连接标识
    # 	 @param param 天线端口||0x01,选择灭活参数 & 0x02,标签灭活密码
    @staticmethod
    def DestroyGB(connID, param):
        rt = ""
        getStatus = Frame_0010_53(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_53,3000)
        if response != None:
            rt = response.GetReturnData()
        return rt

    @staticmethod
    def QtTagOption(connID, param):
        rt = ""
        getStatus = Frame_0010_14(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_14, 3000)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   获取天线功率
    # 	 * @return 1,27&2,30 ( 一号天线功率27，2号天线30 )
    @staticmethod
    def GetPower(connID, param):
        rt = RFIDReader._GetError
        getStatus = Frame_0010_02(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_02)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   设置天线功率
    # 	 * @return "1:21&2:21&3:21&4:21"
    @staticmethod
    def SetPower(connID, param):
        rt = RFIDReader._GetError
        getStatus = Frame_0010_01(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_01)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   获取基带参数
    # 	 * @return 0~255 | 0~255 |  0~255 | 0~255
    @staticmethod
    def GetBaseband(connID):
        rt = RFIDReader._GetError
        getStatus = Frame_0010_0C()
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_0C)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   设置基带参数
    # 	 * @return 1,0~255 & 2,0~255 & 3,0~255 & 4,0~255
    @staticmethod
    def SetBaseband(connID, param):
        rt = RFIDReader._GetError
        getStatus = Frame_0010_0B(param)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_0B)
        if response != None:
            rt = response.GetReturnData()
        return rt

    @staticmethod
    def GetBasebandX(connID):
        rt = RFIDReader._GetError
        try :
            getStatus = Frame_0010_E1()
            RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
            response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_E1)
            if response != None:
                rt = response.GetReturnData()
        except Exception as e:
            rt = Param_Option.Param_Option.S_EXCPTION
        return rt

    @staticmethod
    def SetBasebandX(connID,param):
        rt = RFIDReader._GetError
        try:
            getStatus = Frame_0010_E0(param)
            RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
            response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_E0)
            if response != None:
                rt = response.GetReturnData()
        except Exception as e:
            rt = Param_Option.Param_Option.S_EXCPTION
        return rt

    #   获取天线功率
    # 	 * @return 0，国标920~925MHz 1，国标840~845MHz 2，国标840~845MHz和920~925MHz 3，FCC，902~928MHz ETSI，866~868MHz
    @staticmethod
    def GetFrequency(connID):
        rt = RFIDReader._GetError
        getStatus = Frame_0010_04()
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_04)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   设置天线功率
    # 	 * @return 0，国标920~925MHz 1，国标840~845MHz 2，国标840~845MHz和920~925MHz 3，FCC，902~928MHz ETSI，866~868MHz
    @staticmethod
    def SetFrequency(connID):
        rt = RFIDReader._GetError
        getStatus = Frame_0010_03()
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_03)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   设置标签上传参数
    # 	 * @param param 1,0~65535 & 2,0~255
    # 	 * @return 返回是否成功
    @staticmethod
    def SetTagUpdateParam(connID):
        rt = RFIDReader._GetError
        getStatus = Frame_0010_09()
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_09)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   配置GPO状态
    # 	 * @param connID 连接标识
    # 	 * @param param （1,0 & 2,0 & 3,0 & 4,0）一共4路GPO口 参数0为关闭，1为打开。
    # 	 * @return 返回是否成功
    @staticmethod
    def SetReaderGPOState(connID):
        rt = RFIDReader._GetError
        getStatus = Frame_0001_09()
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0001_09)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   获得读写器的读写能力
    # 	 * @return 最小发射功率|最大发射功率|天线数目|频段列表|RFID协议列表
    @staticmethod
    def GetReaderProperty(connID):
        rt = RFIDReader._GetError
        getStatus = Frame_0010_00()
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0010_00)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   恢复出厂设置
    # 	 * @param param 0X5AA5A55A
    @staticmethod
    def SetReaderRestoreFactory(connID,param):
        return Param_Option.Param_Option.SetReaderRestoreFactory(connID, param)

    #   发射载波
    @staticmethod
    def Set_0101_00(connID,antenna_Port,frequency_Number):
        rt = RFIDReader._GetError
        getStatus = Frame_0101_00(antenna_Port,frequency_Number)
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0101_00)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   驻波检测
    @staticmethod
    def Get_0101_05(connID):
        rt = RFIDReader._GetError
        getStatus = Frame_0101_05()
        RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
        response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0101_05)
        if response != None:
            rt = response.GetReturnData()
        return rt

    #   升级基带软件
    # 	 * @return 是否成功
    @staticmethod
    def UpdateSoft(connID):
        rt = False
        try:
            pass
            fs = open(RFIDReader._UpdateFilePath)
        except Exception as e:
            pass

    #   更新基带软件,一包数据，单包数据不能超1024(协议限制)
    # 	 * @param dataIndex 升级数据编号0x00000000 开始，0xFFFFFFFF 结束。
    # 	 * @param param 升级数据内容
    @staticmethod
    def UpdateBaseband(connID,dataIndex, param):
        rt = ""
        getStatus = Frame_0100_01(dataIndex, param)
        for i in range(0,3):
            RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(getStatus)
            response = RFIDReader.HP_CONNECT.get(connID).WaitResponse(Frame_0100_01, 3000)
            if response != None:
                rt = response.GetReturnData()
            if rt != "":
                break
        return rt

    #   获取返回int值
    @staticmethod
    def GetReturnData(msg):
        rt = -1
        try:
            strArr = msg.rstrip("|").split("|")
            rt = int(strArr[0])
        except Exception as e:
            print(str(e))
        return rt

    #   发送自定义命令
    @staticmethod
    def SendCustomCommand(connID , param):
        rt = ""
        try:
            list = []
            list.append(0xAA)
            crc_Data = Helper_String.hexStringToBytes(param)
            list.append(Helper_String.BytesToArraylist(crc_Data))
            crc = Helper_Protocol.CRC16_8005(crc_Data, len(crc_Data))
            list.append(Helper_String.BytesToArraylist(crc))
            bf = BaseFrame(Helper_String.ArraylisttoBytes(list))
            if bf != None:
                RFIDReader.HP_CONNECT.get(connID).SendSingleFrame(bf)
            rtFrame = RFIDReader.HP_CONNECT.get(connID).WaitResponse(BaseFrame, 2000)
            rt = rtFrame.GetReturnData(rtFrame)
        except Exception as e:
            rt = ""
        return  rt

    #   开始搜索设备
    # 	设备数据信息回调接口
    #   是否启动成功
    @staticmethod
    def StartSearchDevice(msg):
        rt = False
        try:
            # _DeviceSearch = DeviceSearch(msg)
            # _DeviceSearch.Start()
            rt = True
        except Exception as e:
            print("Debug", "搜索设备发生异常" + str(e))
        return rt

    #   停止搜索设备
    @staticmethod
    def StopSearchDevice():
        try:
            if RFIDReader._DeviceSearch != None:
                RFIDReader._DeviceSearch.Stop()
        except Exception as e:
            pass

    #   开启服务器监听
    #   serverIP:服务器监听的IP
    #   return:启动是否成功
    @staticmethod
    def OpenTcpServer(serverIP, serverPort,log):
        pass

    #   关闭服务器监听
    @staticmethod
    def CloseTcpServer():
        pass

    #   获得服务器是否正在启动
    #   true,监听中|false,未监听
    @staticmethod
    def GetServerStartUp():
        pass

    @staticmethod
    def SetAPILanguageType(typeCode):
        Param_Option.Param_Option.ChangeLanguage(typeCode)
        RFID_Option.ChangeLanguage(typeCode)



