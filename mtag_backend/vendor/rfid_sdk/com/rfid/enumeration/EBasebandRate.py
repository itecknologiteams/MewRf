from enum import Enum

#   基带速率枚举
class EBasebandRate(Enum):
    Tari_25us_FM0_BLF_40KHz = 0
    Tari_25us_Miller4_BLF_250KHz = 1
    Tari_25us_Miller4_BLF_300KHz = 2
    Tari_6_25us_FM0_BLF_400KHz = 3
    Tari_20us_Miller4_BLF_320KHz = 4
    Tari_6_25us_Miller2_BLF_320KHz = 5
    Tari_12_5us_FM0_BLF_80KHz = 6
    Tari_7_5us_FM0_BLF_640KHz = 7
    Tari_7_5us_Miller2_BLF_640KHz = 8
    Tari_7_5us_Miller4_BLF_640KHz = 9
    Tari_15us_Miller2_BLF_320KHz = 10
    Tari_20us_Miller2_BLF_320KHz = 11
    Tari_20us_Miller4_BLF_250KHz = 12
    Tari_20us_Miller8_BLF_160KHz = 13
    Auto = 255