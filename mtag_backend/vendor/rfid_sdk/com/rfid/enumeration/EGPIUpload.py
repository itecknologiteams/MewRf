from enum import Enum

# GPI参数 上传枚举
class EGPIUpload(Enum):
    Upload_Start_Trigger_Msg = 0
    Upload_Trigger_Msg = 1
    No_Upload_Trigger_Msg = 2
    No_Upload_Trigger_Msg_Resp = 3