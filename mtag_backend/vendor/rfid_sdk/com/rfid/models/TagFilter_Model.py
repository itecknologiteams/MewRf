#   标签过滤实体类
class TagFilter_Model:
    def __init__(self,*dataValue):
        self.Bank = None
        self.tagStart= None
        self.data = None
        if len(dataValue) == 1:
            self.Bank = dataValue[0]
        elif len(dataValue) == 3:
            self.Bank = dataValue[0]
            self.tagStart = dataValue[1]
            self.data = dataValue[2]