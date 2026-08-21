import threading
import time
import serial
from com.rfid.helper.Helper_String import Helper_String
from gmssl import func
from com.rfid.connect.BaseConnect import BaseConnect

# 串口通讯类
class SerialConnect(BaseConnect):

    def __init__(self,portName, baudRate):
        super().__init__()
        self._PortName = portName
        self._BaudRate = baudRate
        self._ConnectName = portName + ":" + str(baudRate)
        self.serialConn = None
        self.sendLock = threading.Lock()

    # 获取连接状态
    def IsConnected(self):
        return self._IsConnect

    # 打开链接RO_ReaderInformation
    def OpenConnect(self):
        try:
            self.serialConn = serial.Serial(self._PortName, self._BaudRate)
            self.serialConn.write_timeout = 2  # 设置写操作的超时时间为2秒
            self._IsConnect = True
            self._IsStartReceive = True
            self._ConnectType = 4
            if self.serialConn.isOpen():
                # 开始接收数据
                self.StartReceive()
                # 开始处理数据
                self.StartProcess()
                return True
            else:
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
            if self.serialConn is not None and self.serialConn.isOpen:
                self.serialConn.close()
            self.serialConn = None
        except Exception as e:
            print('Close Serial Exception:' + str(e))

    # 发送单条指令
    def SendSingleFrame(self,bf):
        try:
            if self._IsConnect and self._IsStartReceive:
                if self._Is485 :
                    bf._CW._CW_13 = "1"
                    bf._Serial_Mac = self._485Mac
                    sendData = bf.GetFreamData(True)
                else:
                    sendData = bf.GetFreamData(False)
                # print("发送消息")
                # print(func.bytes_to_list(sendData))
                with self.sendLock:
                    self.serialConn.write(sendData)
                self.myLog.WriteDebugMsg(self._ConnectName, "Send: " + Helper_String.PrintHexStringByteSum(sendData))
                return True
        except Exception as e:
            print('Close Serial Exception:' + str(e))
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
                data = self.serialConn.read(self.serialConn.inWaiting()) # self.serialConn.inWaiting()
                if len(data) != 0:
                    receiveBuffer = func.bytes_to_list(data)  # bytes转list
                    # print("接收消息")
                    # print(receiveBuffer)
                    with self._LockReceiveBuffer:
                        while len(receiveBuffer) + self.receiveBufferManager.DataCount > self.MAX_BUFFER_LEN:
                            self._LockReceiveBuffer.wait(10000)
                        self.receiveBufferManager.WriteBuffer(receiveBuffer, 0, len(receiveBuffer))  # 将接收到的数据放入缓存区
                        self._LockReceiveBuffer.notify()
                time.sleep(0.1)
            except Exception as e:
                if self.myLog != None:
                    self.myLog.WriteDebugMsg(self._ConnectName, "StartReceive(): " + str(e))
                    self.myLog.PortClosing(self._ConnectName)
                self.CloseConnect()
                break