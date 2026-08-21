
# EPC基带参数
class EpcBaseband_Model:

    def __init__(self,*data):
        self.eBasebandRate = None
        self.qValue = None
        self.session = None
        self.searchType = None
        if data and len(data) == 4:
            self.eBasebandRate = data[0]
            self.qValue = data[1]
            self.session = data[2]
            self.searchType = data[3]
