# Reader LED
class ReaderLED_Model:
    def __init__(self,*data):
        # LED灯是否开启。True为开启
        self.LEDSwitch = None
        # 开启时间，单位毫秒。
        self.LEDTime = None
        if data:
            self.LEDSwitch = data[0]
            self.LEDTime = data[1]

    # 控制LED灯亮起
    # @param time 亮起持续时间，毫秒
    def LEDOpen(self,time):
        self.LEDSwitch = True
        self.LEDTime = time