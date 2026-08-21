from com.rfid.enumeration.EWorkMode import EWorkMode

# Reader 服务器/客户端模式配置
class ReaderWorkMode_Model:
    def __init__(self,*data):
        self.workMode = None
        self.ip = None
        self.port = None
        if len(data) == 1:
            # 配置服务器模式
            self.workMode = EWorkMode.Server
            self.port = data[0]
        elif len(data) == 2:
            # 配置客户端模式
            self.workMode = EWorkMode.Client
            self.ip = data[0]
            self.port = data[1]
        elif len(data) == 3:
            self.workMode = data[0]
            self.ip = data[1]
            self.port = data[2]