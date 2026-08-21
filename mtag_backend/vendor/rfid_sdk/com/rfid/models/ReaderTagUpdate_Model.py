
# 标签上传参数实体
class ReaderTagUpdate_Model:
    def __init__(self,*data):
        # 重复标签上传过滤时间
        self.repeatTimeFilter = None
        # RSSI 过滤
        self.rssiFilter = None
        # dBm过滤
        self.dBmFilter = None
        if len(data) == 2:
            self.repeatTimeFilter = data[0]
            self.rssiFilter = data[1]
        elif len(data) == 3:
            self.repeatTimeFilter = data[0]
            self.rssiFilter = data[1]
            self.dBmFilter = data[2]