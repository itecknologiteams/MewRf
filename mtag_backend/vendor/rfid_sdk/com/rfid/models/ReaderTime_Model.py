
# ReaderTime_Model
class ReaderTime_Model:
    def __init__(self, *data):
        # 时间
        self.UTC = None
        # NTP是否启用开关
        self.NTP_Switch = False
        self.IP = ""
        if len(data) == 1:
            # 仅配置时间
            self.UTC = data[0]
        elif len(data) == 2:
            # 仅配置NTP
            self.NTP_Switch = data[0]
            self.IP = data[1]
        elif len(data) == 3:
            self.UTC = data[0]
            self.NTP_Switch = data[1]
            self.IP = data[2]
