
# Reader 蜂鸣器
from com.rfid.enumeration.EBuzzerControl import EBuzzerControl
from com.rfid.enumeration.EBuzzerType import EBuzzerType


class ReaderBuzzer_Model:
    def __init__(self,*data):
        self.buzzerControl = None
        self.buzzerSwitch = None
        self.buzzerType = None
        if data:
            self.buzzerControl = data[0]
            self.buzzerSwitch = data[1]
            self.buzzerType = data[2]

    # 设置蜂鸣器响一次
    def buzzerOnlyOne(self):
        self.buzzerControl = EBuzzerControl.PCControl
        self.buzzerSwitch = True
        self.buzzerType = EBuzzerType.Once

    # 设置蜂鸣器常响
    def buzzerAlways(self):
        self.buzzerControl = EBuzzerControl.PCControl
        self.buzzerSwitch = True
        self.buzzerType = EBuzzerType.Always
    # 关闭蜂鸣器
    def buzzerStop(self):
        self.buzzerSwitch = False
        self.buzzerType = EBuzzerType.Once