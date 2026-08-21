

# AST扩展参数
class ASTExtendedParam_Model:
    def __init__(self,*data):
        # 天线切换模式
        self.antSwitchMode = None
        # 重试次数（无标签认定的重试次数，天线切换的一个参考选项）
        self.retry = None
        # 天线驻留最大时间（x10ms）
        self.residenceTime = None
        if data and len(data) == 3:
            self.antSwitchMode = data[0]
            self.retry = data[1]
            self.residenceTime = data[2]