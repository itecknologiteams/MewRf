import time

from com.rfid.helper.Helper_Protocol import Helper_Protocol

# GPI红外回调信息
class GPI_Model:
    def __init__(self,*data):
        self.GpiIndex = None
        self.GpiState = None
        self.StartOrStop = None
        self.ReaderName = None
        self.UTC = None
        self.UtcTime = None

        if data:
            self.ReaderName = data[0]
            self.GpiIndex = data[1] + 1 # 加1是为了使GPIindex从1开始
            self.GpiState = data[2]
            self.StartOrStop = data[3]
            self.UTC = data[4]
            utc = Helper_Protocol.ReverseU32BytesToInt(self.UTC, 0) * 1000 + Helper_Protocol.ReverseU32BytesToInt(self.UTC, 4) / 1000;

            timeArray = time.localtime(utc/1000)
            self.UtcTime = time.strftime("%Y-%m-%d %H:%M:%S", timeArray)

