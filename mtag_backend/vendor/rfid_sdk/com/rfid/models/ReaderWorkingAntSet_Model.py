
# 读写器读的时候所用天线
class ReaderWorkingAntSet_Model:
    def __init__(self,*data):
        # 所用天线数组
        self.antennaList = None
        if data:
            self.antennaList = data[0]

