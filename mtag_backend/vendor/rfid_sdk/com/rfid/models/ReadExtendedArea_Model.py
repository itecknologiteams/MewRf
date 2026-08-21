
# 读写器 读取扩展区
class ReadExtendedArea_Model:
    def __init__(self,*data):
        self.bank = None
        self.readStart = None
        self.readLen = None
        self.passWord = None
        if data:
            self.bank = data[0]
            self.readStart = data[1]
            self.readLen = data[2]
            self.passWord = data[3]
