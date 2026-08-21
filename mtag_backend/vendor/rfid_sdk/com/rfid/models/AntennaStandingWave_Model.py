
# 天线检测驻波类
class AntennaStandingWave_Model:

    def __init__(self,ant):
        # 天线
        self.antNum = ant
        # 前向功率检测值
        self.forwardPower = None
        # 后向功率检测值
        self.backwardPower = None
        # 回波损耗
        self.returnLoss = None
        # 驻波比
        self.standingWaveRatio = None
