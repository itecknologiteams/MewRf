from enum import Enum

#   锁区域枚举
class ELockArea(Enum):
    DestroyPassword = 0
    AccessPassword = 1
    epc = 2
    tid = 3
    userdata =4