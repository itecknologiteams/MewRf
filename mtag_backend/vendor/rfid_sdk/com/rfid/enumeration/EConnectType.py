from enum import Enum

#   连接类型枚举
class EConnectType(Enum):
    _TcpConn = 0
    _SerialConn = 1
    _485Conn = 2
    _UsbConn = 3