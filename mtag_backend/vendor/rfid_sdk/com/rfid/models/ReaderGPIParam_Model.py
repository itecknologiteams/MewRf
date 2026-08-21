

# Reader GPI/O 信息
class ReaderGPIParam_Model:
    def __init__(self,*data):
        # 触发GPI端口号
        self.GPINum = None
        # 触发开始条件
        self.triggerStart = None
        # 触发执行指令
        self.triggerCode = None
        # 触发停止条件
        self.triggeerStop = None
        # 停止延时时间
        self.delayTime = None
        # 上传标志
        self.isUpload = None
        # 客户代码指令
        self.customTriggerCode = None

        if len(data) == 1:
            self.GPINum = data[0]
        elif len(data) == 7:
            self.GPINum = data[0]
            self.triggerStart = data[1]
            self.triggerCode = data[2]
            self.triggeerStop = data[3]
            self.delayTime = data[4]
            self.isUpload = data[5]
            self.customTriggerCode = data[6]


