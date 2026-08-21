from abc import ABCMeta, abstractmethod
# 主动上传消息接口，上传所有模块主动上传的指令

# 异步回调信息接口
class IAsynchronousMessage:
    __metaclass__ = ABCMeta # 指定这是一个抽象类  

    '''
    输出调试信息
    @param msg 调试信息
    '''
    @abstractmethod
    def WriteDebugMsg(self,connID,msg):
        pass

    '''
    输出日志信息
    @param msg 日志信息
    '''
    @abstractmethod
    def WriteLog(self,connID, msg):
        pass

    '''
    TCP服务器模式下的，客户端连接回调
    即读写器工作在TCP Client模式下主动连接Server，Server上面的程序作为TCP server监听从读写器主动发出来的连接请求。
    @param connID 连接标识
   '''
    @abstractmethod
    def PortConnecting(self,connID):
        pass

    '''
    连接断开回调。当设备连接断开时，API 会回调连接 ID，表明当前连接 ID 的设备已经断开连接。
    @param connID 连接标识
    '''
    @abstractmethod
    def PortClosing(self,connID):
        pass

    '''
    输出标签信息回调
    @param tag 标签信息
    '''
    @abstractmethod
    def OutputTags(self,tag):
        pass

    '''
    EPC读卡结束通知, 表明当前读取标签动作结束
    '''
    @abstractmethod
    def OutputTagsOver(self,connID):
        pass

    '''
    GPI触发消息回调
    @param gpi_model GPI信息类
    '''
    @abstractmethod
    def GPIControlMsg(self,connID,gpi_model):
        pass

    '''
    输出蓝牙手持机的扫码数据回调
    @param scandata 扫描的数据
    '''
    @abstractmethod
    def OutputScanData(self,connID,scandata):
        pass
