from enum import Enum

# 读写区域枚举
class EReadBank(Enum):
    EPC = 0
    TID = 1
    UserData = 2
    Reserved = 3
    EpcData = 4