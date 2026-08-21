from enum import Enum

#   锁类型枚举·1
class ELockType(Enum):
    Unlock = 0
    Lock = 1
    PermanentUnlock = 2
    PermanentLock = 3
