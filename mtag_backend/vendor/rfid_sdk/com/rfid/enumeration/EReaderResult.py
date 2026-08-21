from enum import Enum

# 方法返回枚举
class EReaderResult(Enum):
    # 操作成功
    RT_OK = 0
    # 操作失败
    RT_FAILED_ERR = 1
    # 系统错误
    RT_SYSTEM_ERR = 2
    # 不支持的操作
    RT_NOT_SUPPORTED_ERR = 3
    # 参数错误
    RT_INVALID_PARA_ERR = 4
    # 读写器响应超时
    RT_TIMEOUT_ERR = 5
    # 读写器未连接
    RT_NOT_CONNECT_ERR = 6
    # 过滤器错误
    RT_NOT_FILTER_ERR = 7
    # 此区域已锁定
    RT_AREA_LOCKED_ERR = 8
    # 未连接，驻波比：无穷大
    RT_NOT_CONNECT_INFINITY_ERR = 9
    # 标签丢失
    RT_TAG_LOSS_ERR = 10
    # 销毁密码错误
    RT_TAG_DESTORY_PASS_ERR = 11