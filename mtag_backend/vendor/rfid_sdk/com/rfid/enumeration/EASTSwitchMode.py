from enum import Enum

#   天线切换模式枚举
class EASTSwitchMode(Enum):
    #   无标签立即切换
    Switch_Immediately_Without_Tags = 0
    #   用完驻留时间
    Running_Out_Of_Residence_Time = 1