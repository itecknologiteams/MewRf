
# 通用 传递字符串类型对象
class ReaderString_Model:
    def __init__(self,*dataValue):
        self.data = ""
        if dataValue:
            self.data = dataValue[0]