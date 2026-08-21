from enum import Enum

#   天线枚举
class EAntennaNo(Enum):
    _1 = 1
    _2 = 2
    _3 = 4
    _4 = 8
    _5 = 16
    _6 = 32
    _7 = 64
    _8 = 128
    _9 = 256
    _10 = 512
    _11 = 1024
    _12 = 2048
    _13 = 4096
    _14 = 8192
    _15 = 16384
    _16 = 32768
    _17 = 65536
    _18 = 131072
    _19 = 262144
    _20 = 524288
    _21 = 1048576
    _22 = 2097152
    _23 = 4194304
    _24 = 8388608

    @staticmethod
    def getValue(index):
        if index == 1:
            return EAntennaNo._1
        elif index == 2:
            return EAntennaNo._2
        elif index == 3:
            return EAntennaNo._3
        elif index == 4:
            return EAntennaNo._4
        elif index == 5:
            return EAntennaNo._5
        elif index == 6:
            return EAntennaNo._6
        elif index == 7:
            return EAntennaNo._7
        elif index == 8:
            return EAntennaNo._8
        elif index == 9:
            return EAntennaNo._9
        elif index == 10:
            return EAntennaNo._10
        elif index == 11:
            return EAntennaNo._11
        elif index == 12:
            return EAntennaNo._12
        elif index == 13:
            return EAntennaNo._13
        elif index == 14:
            return EAntennaNo._14
        elif index == 15:
            return EAntennaNo._15
        elif index == 16:
            return EAntennaNo._16
        elif index == 17:
            return EAntennaNo._17
        elif index == 18:
            return EAntennaNo._18
        elif index == 19:
            return EAntennaNo._19
        elif index == 20:
            return EAntennaNo._20
        elif index == 21:
            return EAntennaNo._21
        elif index == 22:
            return EAntennaNo._22
        elif index == 23:
            return EAntennaNo._23
        elif index == 24:
            return EAntennaNo._24

    @staticmethod
    def getIndex(enum):
        if enum == EAntennaNo._1:
            return 1
        elif enum == EAntennaNo._2:
            return 2
        elif enum == EAntennaNo._3:
            return 3
        elif enum == EAntennaNo._4:
            return 4
        elif enum == EAntennaNo._5:
            return 5
        elif enum == EAntennaNo._6:
            return 6
        elif enum == EAntennaNo._7:
            return 7
        elif enum == EAntennaNo._8:
            return 8
        elif enum == EAntennaNo._9:
            return 9
        elif enum == EAntennaNo._10:
            return 10
        elif enum == EAntennaNo._11:
            return 11
        elif enum == EAntennaNo._12:
            return 12
        elif enum == EAntennaNo._13:
            return 13
        elif enum == EAntennaNo._14:
            return 14
        elif enum == EAntennaNo._15:
            return 15
        elif enum == EAntennaNo._16:
            return 16
        elif enum == EAntennaNo._17:
            return 17
        elif enum == EAntennaNo._18:
            return 18
        elif enum == EAntennaNo._19:
            return 19
        elif enum == EAntennaNo._20:
            return 20
        elif enum == EAntennaNo._21:
            return 21
        elif enum == EAntennaNo._22:
            return 22
        elif enum == EAntennaNo._23:
            return 23
        elif enum == EAntennaNo._24:
            return 24
