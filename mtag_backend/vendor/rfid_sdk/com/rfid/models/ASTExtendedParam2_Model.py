

# AST2扩展参数
class ASTExtendedParam2_Model:
    def __init__(self,*data):
        # 天线切换等待时间(x10ms)
        self.waitingTime = None
        # 天线切换步进值
        self.antStep = None
        # 天线保护阀值（回波损耗dBm），设置为0不启用保护。
        self.antThreshold = None
        if data and len(data) == 3:
            self.waitingTime = data[0]
            self.antStep = data[1]
            self.antThreshold = data[2]



