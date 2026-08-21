

# 天线配置(功率、使能)
from com.rfid.enumeration.EAntennaNo import EAntennaNo


class ReaderAntPower_Model:
    def __init__(self,*data):
        self.antennaNo = None
        self.power = None
        self.enable = None
        if data:
            self.antennaNo = data[0]
            self.power = data[1]
            self.enable = data[2]

    #批量生成天线对象
    # @ param aPower 功率
    # @ param aEnable 使能
    # @ paramantNo 天线号
    @staticmethod
    def AntPowerAllConfig(aPower,aEnable,*antNo):
        try:
            readerAntPowerModels = []
            for i in antNo:
                readerAntPowerModel = ReaderAntPower_Model(EAntennaNo.getValue(i), aPower, aEnable)
                readerAntPowerModels.append(readerAntPowerModel)
            return readerAntPowerModels
        except Exception as e:
            print("方法AntPowerAllConfig失败，错误信息%s" % e)
            return None


