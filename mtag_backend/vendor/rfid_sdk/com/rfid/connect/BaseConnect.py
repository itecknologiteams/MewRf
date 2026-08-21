import _thread
import threading
import time
from abc import ABCMeta, abstractmethod
from concurrent.futures import thread
from queue import Queue

from com.rfid.connect.RingBufferManager import RingBufferManager
from com.rfid.enumeration.ECallBack import ECallBack
from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.models.GPI_Model import GPI_Model
from com.rfid.models.Tag_Model import Tag_Model
from com.rfid.protocol.BaseFrame import BaseFrame
from com.rfid.protocol.Frame_0001_12 import Frame_0001_12
from com.rfid.protocol.Frame_0001_1D import Frame_0001_1D

# 模块连接基类
class BaseConnect:
    def __init__(self):
        # 默认超时时间 毫秒
        self.DEFAULT_TIMOUT = 1500
        # 接收消息最大缓存大小（字节）
        self.MAX_BUFFER_LEN = 1024 * 1024
        # 接收数据区缓存管理
        self.receiveBufferManager = RingBufferManager(self.MAX_BUFFER_LEN)

        # 单次接收缓存大小
        self.receiveBufferLen = 1024
        # 处理主动上传消息总条数
        self.ProcessCount = 0
        # 接收缓存线程锁
        self._LockReceiveBuffer = threading.Condition()
        # 当前处理的最后一条被动上传的消息帧，接收到回复后请置为null;
        self.lastProcessFrame = None
        # 被动上传的消息锁
        self._LockLastProcessFrame = threading.Condition()
        # 是否继续循环接收数据
        self._IsStartReceive = True
        # 处理主动上传消息接口对象
        self.myLog = None
        self._LastHeartTime = time.time()

        # 是否已连接成功
        self._ConnectName = ""
        # 连接类型，1 串口连接，2 TCP客户端连接，3 TCP服务端连接 4 USB连接
        self._ConnectType = -1

        # 断线是否自动重连
        self._IsReConnect = True
        # 是否是485通信
        self._Is485 = False
        # 485地址
        self._485Mac = 0
        self._ReaderSN = ""

        # 回调消息队列同步锁
        self.CallBackQueueLock = threading.Lock()
        # 回调消息队列
        self.CallBackQueue = Queue()
        # 同步对象
        self.LastProcessFrameLock = threading.Lock()
        # 当前处理的最后一条被动上传的消息帧
        self.LastProcessFrame = None
        # 循环读6B加6C标签
        self.Is6B_6C_Start = True
        # 循环读6B加6C标签线程锁
        self._6B_6CLock = threading.Lock()

    # 获取连接状态
    @abstractmethod
    def IsConnected(self):
        pass

    # 打开连接
    @abstractmethod
    def OpenConnect(self):
        pass

    # 关闭连接
    @abstractmethod
    def CloseConnect(self):
        pass

    # 发送单条指令
    @abstractmethod
    def SendSingleFrame(self, bf):
        pass

    # 开始接收数据
    @abstractmethod
    def StartReceive(self):
        pass

    # 开始处理接收到的数据
    def StartProcess(self):
        myrec = threading.Thread(target=self.prcThread)
        myrec.start()

    def prcThread(self):
        self._LastHeartTime = time.time()
        # 设置名字，调整优先级，缺失--------
        # print("Debug", "---Process Start---")
        # 插入0xFF的长度
        ffCount = 0
        # 分包
        while self._IsStartReceive:
            freame_byte = None
            with self._LockReceiveBuffer:
                dataLen = 0
                try:
                    if self.receiveBufferManager.DataCount <= 7:  # 数据不满一帧
                        self._LockReceiveBuffer.wait()
                        continue
                    if (self.receiveBufferManager.Index(0) & 0xFF) != 0xAA:  # 寻找数据起始帧
                        self.receiveBufferManager.Clear(1)
                        continue
                    else:
                        lenIndex = 5  # 数据长度结束位置
                        if self._Is485:  # 485通信帧长度+1;
                            lenIndex += 1
                        len_byte = bytearray(lenIndex)
                        self.receiveBufferManager.ReadBuffer(len_byte, 0, len(len_byte))
                        dataLen = Helper_Protocol.U16BytesToInt(len_byte, lenIndex - 2)  # 网络字节序转换成本地字节序
                        if dataLen < 0 or dataLen > 1024:
                            self.receiveBufferManager.Clear(1)
                            print("Debug", "data length over range!")
                            continue
                        frameLen = dataLen + lenIndex + 2  # 帧头1 + 协议控制字2 + 数据长度2 + 校验码2
                        if self.receiveBufferManager.DataCount < frameLen:
                            self._LockReceiveBuffer.wait()
                            continue
                        else:
                            freame_byte = bytearray(frameLen)
                            self.receiveBufferManager.ReadBuffer(freame_byte, 0, frameLen)
                            self.receiveBufferManager.Clear(frameLen)
                except Exception as e:
                    print("Fail1，BaseConnect Process Exception:%s" % e)
            if freame_byte != None:
                bf = BaseFrame(freame_byte)
                if bf.CheckCRC():
                    if self._Is485 and bf._Serial_Mac != self._485Mac:  # 485数据地址不对
                        continue
                    if bf._CW._CW_12 == "0":
                        if bf._CW._CW_MID == 0x12 and bf._CW._CW_8_11 == "0001":  # 连接状态确认
                            self._LastHeartTime = time.time()
                            continue
                        with self._LockLastProcessFrame:
                            self.lastProcessFrame = bf
                            self._LockLastProcessFrame.notify()
                    else:  # 主动上传消息
                        try:
                            self.ProcessUploadMsg(bf)
                        except Exception as e:
                            print("Fail2，BaseConnect Process Exception:%s" % e)
                        self.ProcessCount += 1

    # 处理主动上传消息
    def ProcessUploadMsg(self, bf):
        # 6C标签数据返回
        if bf._CW._CW_MID == 0x00 and bf._CW._CW_8_11 == "0010":
            tag_6c = Tag_Model(0, bf._Data)
            tag_6c._ReaderName = self._ConnectName
            tag_6c._ReaderSN = self._ReaderSN

            if tag_6c._IsContinue == 1:  # 如果启用断点续传功能，则需要回送标签编号信息
                sendBF = Frame_0001_1D(tag_6c._SerialNo)
                self.SendSingleFrame(sendBF)
            self.myLog.OutputTags(tag_6c)

        # 6B标签数据返回
        elif bf._CW._CW_MID == 0x20 and bf._CW._CW_8_11 == "0010":
            tag_6b = Tag_Model(bf._Data, 1)
            if tag_6b._IsContinue == 1:  # 如果启用断点续传功能，则需要回送标签编号信息
                sendBF = Frame_0001_1D(tag_6b._SerialNo)
                self.SendSingleFrame(sendBF)
            tag_6b._ReaderName = self._ConnectName
            tag_6b._ReaderSN = self._ReaderSN
            self.myLog.OutputTags(tag_6b)

        # 国标标签数据返回
        elif bf._CW._CW_MID == 0x30 and bf._CW._CW_8_11 == "0010":
            tag_gb = Tag_Model(bf._Data, 2)
            if tag_gb._IsContinue == 1:  # 如果启用断点续传功能，则需要回送标签编号信息
                sendBF = Frame_0001_1D(tag_gb._SerialNo)
                self.SendSingleFrame(sendBF)
            tag_gb._ReaderName = self._ConnectName
            tag_gb._ReaderSN = self._ReaderSN
            self.myLog.OutputTags(tag_gb)

        # EPC读卡结束通知
        elif bf._CW._CW_MID == 0x01 and bf._CW._CW_8_11 == "0010":
            self.myLog.OutputTagsOver(self._ConnectName)

        # 6B读卡结束通知
        elif bf._CW._CW_MID == 0x21 and bf._CW._CW_8_11 == "0010":
            self.myLog.OutputTagsOver(self._ConnectName)

        # 国标读卡结束通知
        elif bf._CW._CW_MID == 0x31 and bf._CW._CW_8_11 == "0010":
            self.myLog.OutputTagsOver(self._ConnectName)

        # 连接状态确认
        elif bf._CW._CW_MID == 0x12 and bf._CW._CW_8_11 == "0001":
            tempByte = [0 for x in range(0, 4)]
            Helper_Protocol.arrayCopy(bf._Data, 0, tempByte, 0, 4)
            iNo = Helper_String.ByteArrayToInt(tempByte)
            # sendBF = Frame_0001_12(iNo)  # 返回心跳确认
            # self.myLog.WriteDebugMsg(self._ConnectName, "Rcv Heartbeats: " + Helper_String.ByteToString(bf._Data))
            # self.SendSingleFrame(sendBF)
            # self.myLog.WriteDebugMsg(self._ConnectName, "Send Heartbeats...")

        # GPI触发开始消息
        elif bf._CW._CW_MID == 0x00 and bf._CW._CW_8_11 == "0001":
            b_UTC = [0 for x in range(0, 8)]
            Helper_Protocol.arrayCopy(bf._Data, 2, b_UTC, 0, len(b_UTC))
            gm = GPI_Model(self._ConnectName, bf._Data[0], bf._Data[1], 0, b_UTC)
            self.myLog.WriteDebugMsg(self._ConnectName, str(bf._Data[0]) + "1" + "-GPI Start")
            self.myLog.GPIControlMsg(self._ConnectName, gm)

        # GPI触发停止消息
        elif bf._CW._CW_MID == 0x01 and bf._CW._CW_8_11 == "0001":
            b_UTC = [0 for x in range(0, 8)]
            Helper_Protocol.arrayCopy(bf._Data, 2, b_UTC, 0, len(b_UTC))
            gm = GPI_Model(self._ConnectName, bf._Data[0], bf._Data[1], 1, b_UTC)
            self.myLog.WriteDebugMsg(self._ConnectName, str(bf._Data[0]) + "1" + "-GPI End")
            self.myLog.GPIControlMsg(self._ConnectName, gm)

        # 蓝牙手持机的扫描头主动上传
        elif bf._CW._CW_MID == 0x54 and bf._CW._CW_8_11 == "0001":
            self.myLog.OutputScanData(self._ConnectName, bf._Data)

    # 接收单条数据消息
    def WaitResponse(self, tClass, timout=None):
        if timout == None:
            timout = self.DEFAULT_TIMOUT
        rt = None
        try:
            cName = tClass.__name__
            CW_8_11 = ""
            CW_MID = 0xFF
            try:
                arrName = cName.split("_")
                CW_8_11 = arrName[1]
                CW_MID = Helper_String.hexStringToBytes(arrName[2])[0]
            except Exception as e:
                pass
            rt = tClass  # 创建子类消息对象
            last = None
            with self._LockLastProcessFrame:
                if self.lastProcessFrame != None:
                    if CW_8_11 == self.lastProcessFrame._CW._CW_8_11 and CW_MID == self.lastProcessFrame._CW._CW_MID:
                        last = self.lastProcessFrame
                        self.lastProcessFrame = None
                    else:
                        self.lastProcessFrame = None
                else:
                    for i in range(0, 3):
                        self._LockLastProcessFrame.wait(timout / 3 / 1000)
                        # time.sleep(timout / 3 /1000)
                        if self.lastProcessFrame != None:
                            # 判断返回的指令是否是所需要的指令
                            if CW_8_11 == self.lastProcessFrame._CW._CW_8_11 and CW_MID == self.lastProcessFrame._CW._CW_MID:
                                last = self.lastProcessFrame
                                self.lastProcessFrame = None
                                break
                            else:
                                self.lastProcessFrame = None
                                continue
            # 接收到数据
            if last != None:
                rt._CW = last._CW
                rt._Serial_Mac = last._Serial_Mac
                rt._Data_Len = last._Data_Len
                rt._Data = last._Data
                rt._CRC = last._CRC
            else:
                return None
        except Exception as e:
            print("Fail3，BaseConnect Process Exception:%s" % e)
        return rt

    def WriteDebugMsg(self, msg):
        print("Reader - " + self._ConnectName + ": " + msg)

    # 处理消息队列
    def AddCallBack(self, callBack):
        if callBack._CallBackType == ECallBack.Tag:
            tagModel = callBack._CallBackParam
            if tagModel != None:
                self.myLog.OutputTags(tagModel)
        elif callBack._CallBackType == ECallBack.TagOver:
            with self._6B_6CLock:
                self._6B_6CLock.notifyAll()
            self.myLog.OutputTagsOver(self._ConnectName)
        elif callBack._CallBackType == ECallBack.CommandRec:
            bf = callBack._CallBackParam
            if bf != None:
                with self.LastProcessFrameLock:
                    self.LastProcessFrame = bf
                    self.LastProcessFrameLock.notify()
        elif callBack._CallBackType == ECallBack.GPIO:
            pass
