#   标签输出格式，
class TagData_Model:
    def __init__(self,*dataValue):
        self.Bank = None
        self.tagStart= None
        self.tagLen= None
        self.data = None
        if len(dataValue) == 1:
            self.Bank = dataValue[0]
        elif len(dataValue) == 3:
            self.Bank = dataValue[0]
            self.tagStart = dataValue[1]
            self.tagLen = dataValue[2]
        elif len(dataValue) == 4:
            self.Bank = dataValue[0]
            self.tagStart = dataValue[1]
            self.tagLen = dataValue[2]
            self.data = dataValue[3]