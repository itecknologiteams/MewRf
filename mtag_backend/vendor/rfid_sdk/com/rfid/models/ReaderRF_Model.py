


# 频段频点设置
class ReaderRF_Model:
    def __init__(self,*data):
        # 工作频段
        self.readerWorkFrequency = None
        # 工作模式，true是自动, false是指定频率
        self.RFHoppingMode= None
        # 工作频点
        self.readerWorkPoint = None
        if data:
            self.readerWorkFrequency = data[0]
            self.RFHoppingMode = data[1]
            self.readerWorkPoint = data[2]

    # 配置工作频点
    # @param workPoint 频点数组
    @staticmethod
    def WorkPointConfig(*workPoint):
        try:
            workPoints = []
            for i in workPoint:
                workPoints.append(i)
            return workPoint
        except Exception as e:
            return None
            print("方法getReaderNetWorkParam失败，错误信息%s" % e)