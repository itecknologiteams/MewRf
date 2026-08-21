

from com.rfid.enumeration.ELanguage import ELanguage

#   API语言包
class ReaderLanguage:
    # 语种选择,默认英语
    language = ELanguage.English

    CHINESE_PACK = {"OK": "成功",
                    "Fail": "操作失败",
                    "SystemErr": "系统错误",
                    "NotSupport": "不支持的操作",
                    "InvalidParam": "参数错误",
                    "ReaderTimeOut": "读写器响应超时",
                    "NotConnect": "读写器未连接",
                    "FilterErr": "过滤器错误",
                    "AreaLockedErr": "此区域已锁定",
                    "NoCorrespondErrorCode": "无对应错误编码",
                    "NotConnectInfinityErr": "未连接，驻波比：无穷大",
                    "TagLossErr": "标签丢失",
                    "TagDestoryPassErr":"标签销毁密码错误"}

    ENGLISH_PACK = {"OK": "OK",
                    "Fail": "Fail",
                    "SystemErr": "System Error",
                    "NotSupport": "Not Support",
                    "InvalidParam": "Invalid Param",
                    "ReaderTimeOut": "Reader TimeOut",
                    "NotConnect": "Not Connect",
                    "FilterErr": "Filter Error",
                    "AreaLockedErr": "Area Locked Error",
                    "NoCorrespondErrorCode": "No Correspond Error Code",
                    "NotConnectInfinityErr": "Unconnected, standing wave ratio: infinity",
                    "TagLossErr": "Tag Loss",
                    "TagDestoryPassErr": "Tag Destory Pass Error"}


    #   根据key查翻译
    @staticmethod
    def getString(key):
        if ReaderLanguage.language == ELanguage.Chinese:
            return ReaderLanguage.CHINESE_PACK[key]
        else:
            return ReaderLanguage.ENGLISH_PACK[key]