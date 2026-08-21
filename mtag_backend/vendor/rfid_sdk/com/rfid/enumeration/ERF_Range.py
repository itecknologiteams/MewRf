from enum import Enum

#   频段
class ERF_Range(Enum):
    CHN_920_to_925MHz = 0
    CHN2_840_to_845MHz = 1
    CHN3_920_to_925MHz_and_GB_840_to_845MHz = 2
    FCC_902_to_928MHz = 3
    ETSI_866_to_868MHz = 4
    JPN_916_to_921MHz = 5
    TWN_922_to_927MHz = 6
    IDN_923_to_925MHz = 7
    RUS_866_to_867MHz = 8
    GBT_920_to_925MHz = 9
    KOR_917_to_921MHz = 10
    BRA_908_to_907MHz_and_915MHz_to_928MHz = 11
    MYS_919_to_923MHz = 12
    LKA_920_to_924MHz = 13
    FCC2_902_to_915MHz = 14
    FCC3_915_to_928MHz = 15
    ETSI2_915_to_917MHz = 16
    AUS_920_to_926MHz = 17
    VIE_920_to_923MHz = 18
    ISR_915_to_917MHz = 19
    ZAF_915_to_919MHz = 20
    CUSTOM = 255