from enum import Enum

#   LBT工作模式枚举
class ELBTWorkMode(Enum):
    Disable = 0
    LBT_Listening_Only = 1
    Read_Tag_After_Listening = 2
    Read_Tag_After_Meeting_RSSI = 3