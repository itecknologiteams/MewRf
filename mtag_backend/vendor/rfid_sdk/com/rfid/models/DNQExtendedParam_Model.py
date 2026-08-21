

# DQN扩展参数
class DNQExtendedParam_Model:
    def __init__(self,*data):
        self.maxQ = None
        self.minQ = None
        self.tmult = None
        self.autoQ = False
        self.forceQ = False
        if data and len(data) == 5:
            self.maxQ = data[0]
            self.minQ = data[1]
            self.tmult = data[2]
            self.autoQ = data[3]
            self.forceQ = data[4]

