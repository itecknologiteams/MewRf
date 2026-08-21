from enum import Enum

# 读写器 公开 功能 枚举
class EReaderEnum(Enum):
    # region 可读枚举
    # 读写器信息
    RO_ReaderInformation = 0
    # 天线驻波比
    RO_ReaderAntennaStandingWaveRatio = 1
    # 读写器温度
    RO_ReaderTemperature = 2
    # 查询GPI状态
    RO_ReaderGPIState = 3
    # endregion

    # region Reader读写器配置
    # 串口参数
    RW_ReaderSerialPortParam = 10
    # 485参数
    RW_Reader485Param = 11
    # 网络配置 = IP、子网掩码、网关、MAC地址、DHCP)
    RW_ReaderNetwork = 12
    # 读写器时间 = UTC、NTP)
    RW_ReaderTime = 13
    # 服务器 / 客户端模式参数
    RW_ReaderWorkMode = 14
    # 读写器断点续传
    RW_ReaderBreakPointUpload = 15
    # 蜂鸣器开关
    RW_ReaderBuzzerSwitch = 16
    # 状态指示灯
    RW_ReaderStateLED = 17
    # 标签输出格式
    RW_ReaderDataOutputFormat = 18
    # 自定义编码
    RW_ReaderCustomCode = 19
    # GPI触发参数
    RW_ReaderGPIParam = 20
    # endregion

    # regionRFID配置
    # 天线功率（天线号，功率、使能）
    RW_RFIDAntPower = 101
    # RF配置 = 频段、频点)
    RW_RFIDRF = 102
    # EPC基带参数
    RW_RFIDEpcBasebandParam = 103
    # EPC扩展基带参数
    RW_RFIDEpcBaseExpandBandParam = 104
    # 标签上传参数
    RW_RFIDTagUploadParam = 105
    # 读写器自动空闲模式
    RW_RFIDAutoIdleParam = 106
    # 读写器所用天线配置
    WO_RFIDWorkingAnt = 200
    # 读取扩展区
    WO_RFIDReadExtended = 201
    # 读取特殊区
    WO_RFIDReadSpecial = 202
    # 读取过滤规则
    WO_RFIDReadTagFilter = 203
    # 电平操作
    WO_SetGPOState = 204
    # endregion
    
    Other = 999