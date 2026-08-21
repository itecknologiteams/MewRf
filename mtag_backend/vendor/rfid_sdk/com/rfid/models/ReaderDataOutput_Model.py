

# Reader 标签输出格式类
class ReaderDataOutput_Model:
    def __init__(self,*data):
        self.outputSwitch = None
        self.outputFormat = None
        self.tagData = None
        self.startData = None
        self.endData = None
        if data:
            self.outputSwitch = data[0]
            self.outputFormat = data[1]
            self.tagData = data[2]
            self.startData = data[3]
            self.endData = data[4]