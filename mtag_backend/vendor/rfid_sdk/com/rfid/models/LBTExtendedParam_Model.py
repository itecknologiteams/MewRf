

# LBT扩展参数
class LBTExtendedParam_Model:
    def __init__(self,*data):
        # 工作模式
        self.workMode = None
        # 满足RSSI后才读卡
        self.maxRSSI = None
        if data:
            self.workMode = data[0]
            self.maxRSSI = data[1]

