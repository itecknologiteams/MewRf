
# RS232、RS485查询、配置类。
class ReaderSerial_Model:
    def __init__(self,*data):
        # 485所用地址
        self.address = None
        self.baudrate = None
        if len(data) == 1:
            # RS232、串口构造用
            self.baudrate = data[0]
        elif len(data) == 2:
            # RS485 构造用
            self.address = data[0]
            self.baudrate = data[1]
