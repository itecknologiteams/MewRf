
# 设备信息
class ReaderInfo_Model:
    def __init__(self):
        # 软件版本
        self.softVersion = ""
        # 读写器名称
        self.name = ""
        # 读写器从上电时刻到当前时刻流逝的秒数
        self.powerTime = ""
        # 基带软件版本号
        self.basebandVersion = ""
        # 读写器SN
        self.readerSN = ""
        # 最小功率
        self.minPower = 0
        # 最大功率
        self.maxPower = 0
        # 天线数目
        self.antCount = 0
        # 频段列表
        self.RFList  = []
        # 协议列表
        self.protocolList  = []
        
