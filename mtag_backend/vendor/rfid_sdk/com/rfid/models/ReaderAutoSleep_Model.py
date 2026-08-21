

# 读写器自动空闲模式
class ReaderAutoSleep_Model:
    def __init__(self,*data):
        # 是否开启自动空闲模式
        self.autoIdleSwitch = False
        # 空闲时间
        self.time = 0
        if data:
            self.autoIdleSwitch = data[0]
            self.time = data[1]