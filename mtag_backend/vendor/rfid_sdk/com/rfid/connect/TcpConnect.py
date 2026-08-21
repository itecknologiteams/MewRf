import threading
import time
from socket import socket, AF_INET, SOCK_STREAM

from com.rfid.helper.Helper_String import Helper_String
from gmssl import func
from com.rfid.connect.BaseConnect import BaseConnect

#   TCP 连接读写器
class TcpConnect(BaseConnect):

    def __init__(self,IP,Port):
        super().__init__()
        self.tcpCliSock = None
        self.serverIp = IP
        self.serverPort = Port
        self.sendLock = threading.Lock()

    # 初始化TCP连接
    def Init(self):
        rt = False
        try:
            if self.tcpCliSock != None:
                self.CloseConnect()
            ADDR = (self.serverIp, self.serverPort)
            self.tcpCliSock = socket(AF_INET, SOCK_STREAM)
            self.tcpCliSock.settimeout(3)
            self.tcpCliSock.connect(ADDR)
            self._ConnectName = self.serverIp + ":" + str(self.serverPort)

            self._IsConnect = True # 父类，连接成功
            self._ConnectType = 2  # 父类，连接类型
            rt = True
        except Exception as e:
            print("TCP连接失败！" + str(e))
            self.tcpCliSock = None
            self._IsConnect = False
            self._ConnectType = -1
            rt = False
        return rt

    # 获取连接状态
    def IsConnected(self):
        rt = False
        if self.tcpCliSock != None:
            rt = True
        return rt

    # 打开连接
    def OpenConnect(self):
        try:
            self.Init()
            if self.tcpCliSock != None:
                self._IsStartReceive = True
                # 开始接收数据
                self.StartReceive()
                # 开始处理数据
                self.StartProcess()
                return True
            return False
        except Exception as e:
            print(str(e))
            return False
    # 关闭连接
    def CloseConnect(self):
        try:
            self._IsConnect = False
            self._IsStartReceive = False
            self.tcpCliSock = None
            # self._LockReceiveBuffer.notify()
            self.receiveBufferManager.ClearAll()
        except Exception as e:
            print('Close TCP Exception:' + str(e))

    # 发送单条指令
    def SendSingleFrame(self, bf):
        try:
            if self._IsConnect and self._IsStartReceive:
                sendData = bf.GetFreamData(False)
                # print("发送消息")
                # print(func.bytes_to_list(sendData))
                with self.sendLock:
                    self.tcpCliSock.send((sendData))
                self.myLog.WriteDebugMsg(self._ConnectName, 'Send:' +  Helper_String.PrintHexStringByteSum(sendData))
                return True
        except Exception as e:
            print('Close TCP Exception:' + str(e))
            self.myLog.WriteDebugMsg(self._ConnectName,'Send Exception:' + str(e))
        return False
    # 开始接收数据
    def StartReceive(self):
        myrec = threading.Thread(target = self.rcvThread)
        myrec.start()
    # 接收线程
    def rcvThread(self):
        self._LastHeartTime = time.time()
        while(self._IsConnect and self._IsStartReceive):
            try:
                data = self.tcpCliSock.recv(self.receiveBufferLen)
                receiveBuffer = func.bytes_to_list(data)
                # print("接收消息")
                # print(receiveBuffer)
                with self._LockReceiveBuffer:
                    while len(receiveBuffer) + self.receiveBufferManager.DataCount > self.MAX_BUFFER_LEN:
                        self._LockReceiveBuffer.wait(10000)
                    self.receiveBufferManager.WriteBuffer(receiveBuffer, 0, len(receiveBuffer)) # 将接收到的数据放入缓存区
                    self._LockReceiveBuffer.notify()
                time.sleep(0.1)
            except Exception as e:
                if str(e) == "timed out":
                    continue
                self.CloseConnect()
                from com.rfid import RFIDReader
                RFIDReader.CloseConn(self._ConnectName)
                if self.myLog != None:
                    self.myLog.WriteDebugMsg(self._ConnectName, "StartReceive(): " + str(e))
                    self.myLog.PortClosing(self._ConnectName)



