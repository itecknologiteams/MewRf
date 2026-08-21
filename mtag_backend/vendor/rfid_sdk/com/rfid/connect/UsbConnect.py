import threading
import time

import hid as hid
import usb
from gmssl import func
from com.rfid import RFIDReader
from com.rfid.connect.BaseConnect import BaseConnect
from com.rfid.helper.Helper_String import Helper_String

# USB 连接读写器
class UsbConnect(BaseConnect):
    def __init__(self,usbName):
        super().__init__()
        self._ConnectName = usbName
        self.conn = None
        self.device = None
        self.sendLock = threading.Lock()

    #   初始化
    def Init(self):
        try:
            if self.conn != None:
                self.CloseConnect()
                return False
            nameStr = self._ConnectName.split("ID ")[1]
            vid = nameStr.split(":")[0]
            pid = nameStr.split(":")[1]

            vid = Helper_String.str2hex(vid)
            pid = Helper_String.str2hex(pid)
            self.conn = hid.device()
            self.conn.open(vid, pid)  # TREZOR VendorID/ProductID
            # enable non-blocking mode
            self.conn.set_nonblocking(1)
            self._IsConnect = True
            self._ConnectType = 4
            return True
        except Exception as e:
            print('USB connect Error：' + str(e))
            self.conn = None
            self.device = None
            self._IsConnect = False
            self._ConnectType = -1
        return False

    # 获取连接状态
    def IsConnected(self):
        rt = False
        if self.conn != None:
            rt = True
        return rt

    # 打开连接
    def OpenConnect(self):
        try:
            self.Init()
            if self.conn != None:
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
            self.receiveBufferManager.ClearAll()
            self.device = None

            if self.conn != None:
                self.conn.close()
            self.conn = None
        except Exception as e:
            self.conn = None
            print('Close USB Exception:' + str(e))


    # 发送单条指令
    def SendSingleFrame(self,bf):
        try:
            if self._IsConnect and self._IsStartReceive:
                sendData = bf.GetFreamData(False)
                # print("发送消息")
                # print(func.bytes_to_list(sendData))
                with self.sendLock:
                    self.conn.write(bytearray([0]) + sendData)
                self.myLog.WriteDebugMsg(self._ConnectName, 'Send:' + Helper_String.PrintHexStringByteSum(sendData))
                return True
        except Exception as e:
            print('Close TCP Exception:' + str(e))
            self.myLog.WriteDebugMsg(self._ConnectName,'Send Exception:' + str(e))
        return False

    # 开始接收数据
    def StartReceive(self):
        myrec = threading.Thread(target=self.rcvThread)
        myrec.start()

    # 接收线程
    def rcvThread(self):
        self._LastHeartTime = time.time()
        while (self._IsConnect and self._IsStartReceive):
            try:
                data = self.conn.read(self.receiveBufferLen)
                if len(data) == 0:
                    continue
                receiveBuffer = func.bytes_to_list(data)
                # print("接收消息")
                # print(receiveBuffer)
                with self._LockReceiveBuffer:
                    while len(receiveBuffer) + self.receiveBufferManager.DataCount > self.MAX_BUFFER_LEN:
                        self._LockReceiveBuffer.wait(10000)
                    self.receiveBufferManager.WriteBuffer(receiveBuffer, 0, len(receiveBuffer))  # 将接收到的数据放入缓存区
                    self._LockReceiveBuffer.notify()
                time.sleep(0.1)
            except Exception as e:
                if str(e) == "timed out":
                    continue
                if self.myLog != None:
                    self.myLog.WriteDebugMsg(self._ConnectName, "StartReceive(): " + str(e))
                    self.myLog.PortClosing(self._ConnectName)
                self.CloseConnect()
                RFIDReader.RFIDReader.CloseConn(self._ConnectName)
                if self.myLog != None:
                    self.myLog.PortClosing(self._ConnectName)  # 回调连接关闭消息
                break





