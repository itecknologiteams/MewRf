

# 通用协议帮助类
from com.rfid.helper import Helper_String


class Helper_Protocol:
    CRCtable = [0x0,0x8005,0x800f,0xa,0x801b,0x1e,0x14,0x8011,0x8033,0x36,
                0x3c,0x8039,0x28,0x802d,0x8027,0x22,0x8063,0x66,0x6c,0x8069,
                0x78,0x807d,0x8077,0x72,0x50,0x8055,0x805f,0x5a,0x804b,0x4e,
                0x44,0x8041,0x80c3,0xc6,0xcc,0x80c9,0xd8,0x80dd,0x80d7,0xd2,
                0xf0,0x80f5,0x80ff,0xfa,0x80eb,0xee,0xe4,0x80e1,0xa0,0x80a5,
                0x80af,0xaa,0x80bb,0xbe,0xb4,0x80b1,0x8093,0x96,0x9c,0x8099,
                0x88,0x808d,0x8087,0x82,0x8183,0x186,0x18c,0x8189,0x198,0x819d,
                0x8197,0x192,0x1b0,0x81b5,0x81bf,0x1ba,0x81ab,0x1ae,0x1a4,0x81a1,
                0x1e0,0x81e5,0x81ef,0x1ea,0x81fb,0x1fe,0x1f4,0x81f1,0x81d3,0x1d6,
                0x1dc,0x81d9,0x1c8,0x81cd,0x81c7,0x1c2,0x140,0x8145,0x814f,0x14a,
                0x815b,0x15e,0x154,0x8151,0x8173,0x176,0x17c,0x8179,0x168,0x816d,
                0x8167,0x162,0x8123,0x126,0x12c,0x8129,0x138,0x813d,0x8137,0x132,
                0x110,0x8115,0x811f,0x11a,0x810b,0x10e,0x104,0x8101,0x8303,0x306,
                0x30c,0x8309,0x318,0x831d,0x8317,0x312,0x330,0x8335,0x833f,0x33a,
                0x832b,0x32e,0x324,0x8321,0x360,0x8365,0x836f,0x36a,0x837b,0x37e,
                0x374,0x8371,0x8353,0x356,0x35c,0x8359,0x348,0x834d,0x8347,0x342,
                0x3c0,0x83c5,0x83cf,0x3ca,0x83db,0x3de,0x3d4,0x83d1,0x83f3,0x3f6,
                0x3fc,0x83f9,0x3e8,0x83ed,0x83e7,0x3e2,0x83a3,0x3a6,0x3ac,0x83a9,
                0x3b8,0x83bd,0x83b7,0x3b2,0x390,0x8395,0x839f,0x39a,0x838b,0x38e,
                0x384,0x8381,0x280,0x8285,0x828f,0x28a,0x829b,0x29e,0x294,0x8291,
                0x82b3,0x2b6,0x2bc,0x82b9,0x2a8,0x82ad,0x82a7,0x2a2,0x82e3,0x2e6,
                0x2ec,0x82e9,0x2f8,0x82fd,0x82f7,0x2f2,0x2d0,0x82d5,0x82df,0x2da,
                0x82cb,0x2ce,0x2c4,0x82c1,0x8243,0x246,0x24c,0x8249,0x258,0x825d,
                0x8257,0x252,0x270,0x8275,0x827f,0x27a,0x826b,0x26e,0x264,0x8261,
                0x220,0x8225,0x822f,0x22a,0x823b,0x23e,0x234,0x8231,0x8213,0x216,
                0x21c,0x8219,0x208,0x820d,0x8207,0x202]

    @staticmethod
    def CRC16_CalateByte(CheckByte,LastCRC):
        crcIndex = (((LastCRC & 0xFF00) >> 8) ^ CheckByte) & 0xFF
        return ((LastCRC & 0xFF) << 8) ^ int(Helper_Protocol.CRCtable[crcIndex])
    @staticmethod
    def CRC16_8005(data,len):
        crc_result = 0x0000
        for i in range(0,len):
            crc_result = Helper_Protocol.CRC16_CalateByte(data[i], crc_result)
        rt = Helper_Protocol.ReverseIntToU16Bytes(crc_result)
        return rt
    @staticmethod
    def intToByteArray(a):
        return [
            (bytes)((a >> 24) & 0xFF),
            (bytes)((a >> 16) & 0xFF),
            (bytes)((a >> 8) & 0xFF),
            (bytes)(a & 0xFF)
        ]
    @staticmethod
    def arrayCopy(src, srcPos, dest, destPos, length):
        for i in range(0,length):
            dest[i + destPos] = src[i + srcPos]
    # 将两字节转成 Int
    @staticmethod
    def U16BytesToInt(data,startIndex):
        n = 0
        bData = bytearray(2)
        Helper_Protocol.arrayCopy(data, startIndex, bData, 0, 2)
        mask = 0xff
        temp = 0
        for i in range(0,2):
            n <<= 8
            temp = bData[i] & mask
            n |= temp
        return n
    # 将 Int 转成 两字节网络字节充数组
    @staticmethod
    def ReverseIntToU16Bytes(i):
        rt = bytearray(2)
        rt[0] = 0xff & i
        rt[1] = (0xff00 & i) >> 8
        rt = Helper_Protocol.Reverse(rt)
        return rt
    # 将 Int 转成 两字节数组
    @staticmethod
    def IntToU16Bytes(i):
        rt = [0,0]
        rt[0] = (bytes)(0xff & i)
        rt[1] = (bytes)((0xff00 & i) >> 8)
        return rt

    # 将四字节网络字节序转成
    # data 数据源
    # startIndex 数据数据开始索引源
    @staticmethod
    def ReverseU32BytesToLong(data,startIndex):
        n = 0
        bData = [0,0,0,0]
        Helper_Protocol.arrayCopy(data, startIndex, bData, 0, 4)
        bData = Helper_Protocol.Reverse(bData)
        mask = 0xff
        temp = 0
        for i in range(0,4):
            n <<= 8
            temp = bData[i] & mask
            n |= temp
        return n
    # 将Long 转成 四字节网络字节充数组
    @staticmethod
    def ReverseLongToU32Bytes(i):
        rt = [0,0,0,0]
        rt[0] = (bytes)(0xff & i)
        rt[1] = (bytes)((0xff00 & i) >> 8)
        rt[2] = (bytes)((0xff0000 & i) >> 16)
        rt[3] = (bytes)((0xff000000 & i) >> 24)
        rt = Helper_Protocol.Reverse(rt)
        return rt
    # 将四字节网络字节序转成Int
    # data 数据源
    # startIndex 数据开始索引
    @staticmethod
    def ReverseU32BytesToInt(data,startIndex):
        n = 0
        bData = [0,0,0,0]
        Helper_Protocol.arrayCopy(data, startIndex, bData, 0, 4)
        mask = 0xff
        temp = 0
        for i in range(0,4):
            n <<= 8
            temp = bData[i] & mask
            n |= temp
        return n
    @staticmethod
    def GetS32ByBytes(data,startIndex):
        rt = 0
        try:
            tempByte = bytearray(4)
            Helper_Protocol.arrayCopy(data, startIndex, tempByte, 0, 4)
            rt = Helper_Protocol.ByteArrayToInt(tempByte)
        except Exception as e:
                print("失败，错误信息%s" % e)
                raise Exception
        return rt
    @staticmethod
    def ByteArrayToInt(b):
        return b[3] & 0xFF | (b[2] & 0xFF) << 8 | (b[1] & 0xFF) << 16 | (b[0] & 0xFF) << 24

    @staticmethod
    def Reverse(b):
        temp = bytearray(len(b))
        for i in range(0,len(b)):
            temp[i] = b[len(b) - 1 - i]
        return temp
    @staticmethod
    def EqualsByteArray(source,target):
        if Helper_String.Helper_String.PrintHexStringByteSum(source) == Helper_String.Helper_String.PrintHexStringByteSum(target):
            return True
        return False
    @staticmethod
    def GetHexStringByUInt16(iParam):
        rt = ""
        try:
            rt = Helper_String.Helper_String.PrintHexStringByteSum(Helper_Protocol.ReverseIntToU16Bytes(iParam))
        except Exception as e:
            print("失败，错误信息%s" % e)
        return rt