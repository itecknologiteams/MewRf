import base64
import re

from com.rfid.helper import Helper_Protocol

# 字符串处理帮助类
class Helper_String:
    # 打印字节数组
    @staticmethod
    def PrintHexStringByteSum(b):
        if b:
            sb = ''
            for i in range(0,len(b)):
                hexs = hex(b[i] & 0xFF)[2:]
                if len(hexs) == 1:
                    hexs = '0' + hexs
                sb += hexs.upper() + ""
            return sb
        return None
    # 打印字节
    @staticmethod
    def PrintHexStringByte(b):
        rt = ''
        try:
            rt = hex(b & 0xFF)[2:]
            if len(rt) == 1:
                rt = '0' + str(rt)
        except Exception as e:
            print("失败，错误信息%s" % e)
        return rt

    # 16进制字符串转bytes
    @staticmethod
    def hexStringToBytes(hexString):
        if hexString is None or hexString == "":
            return None
        hexString = hexString.replace(" ", "")
        if (len(hexString) % 2) != 0:
            hexString = "0" + hexString

        hexString = hexString.upper()
        length = int(len(hexString) / 2)
        hexChars = [i for i in hexString]
        d = bytearray(length)
        for i in range(0,length):
            pos = i * 2
            try:
                d[i] = Helper_String.charToByte(hexChars[pos]) << 4 | Helper_String.charToByte(hexChars[pos + 1])
            except:
                d[i] = 256-1
        return d

    @staticmethod
    def str2hex(s):
        odata = 0
        su = s.upper()
        for c in su:
            tmp = ord(c)
            if tmp <= ord('9'):
                odata = odata << 4
                odata += tmp - ord('0')
            elif ord('A') <= tmp <= ord('F'):
                odata = odata << 4
                odata += tmp - ord('A') + 10
        return odata

    @staticmethod
    def charToByte(c):
        return '0123456789ABCDEF'.find(c)

    # 获得网络字节序的U16
    @staticmethod
    def GetReverseU16(data):
        rt = Helper_String.IntToBytesRight(data)
        rt = Helper_String.ArrayReverse(rt)
        return rt

    @staticmethod
    def IntToBytes(s):
        return bytearray([s & 0x00FF, (s & 0xFF00) >> 8])

    @staticmethod
    def IntToBytesRight(s):
        src = bytearray(2)
        src[1] = (s >> 8) & 0xFF
        src[0] = s & 0xFF
        return src

    @staticmethod
    def ArrayReverse(Array):
        new_array = bytearray(len(Array))
        for i in range(0, len(Array)):
            # 反转后数组的第一个元素等于源数组的最后一个元素：
            new_array[i] = Array[len(Array) - i - 1]
        return new_array
    #   byte转成list
    @staticmethod
    def BytesToArraylist(s):
        lst = bytearray()
        for i in s:
            lst.append(i)
        return lst
    #   list转成byte
    @staticmethod
    def ArraylisttoBytes(ins):
        ret = bytearray(len(ins))
        for i in range(0, len(ins)):
            ret[i] = ins[i]
        return ret

    @staticmethod
    def GetU16ByBytes(data, startIndex):
        rt = 0
        try:
            tempByte = bytearray(2)
            Helper_Protocol.Helper_Protocol.arrayCopy(data, startIndex, tempByte, 0, 2)
            rt = int(Helper_String.ByteArrayToInt1(tempByte))
        except Exception as e:
            raise RuntimeError("网络字节序转换成U16异常")
        return rt

    @staticmethod
    def ByteArrayToInt1(b):
        return b[1] & 0xFF | (b[0] & 0xFF) << 8

    @staticmethod
    def ByteArrayToInt(b):
        return b[3] & 0xFF | (b[2] & 0xFF) << 8 | (b[1] & 0xFF) << 16 | (b[0] & 0xFF) << 24

    @staticmethod
    def GetReverseU16String(data):
        return Helper_String.GetReverseU16(int(data))

    # 获得UInt32数据
    # 源数据,起始位置
    @staticmethod
    def GetU32ByBytes(data,startIndex):
        rt = 0
        try:
            tempByte = bytearray(4)
            Helper_Protocol.Helper_Protocol.arrayCopy(data, startIndex, tempByte, 0, 4)
            rt = int(Helper_String.ByteArrayToInt(tempByte))
        except Exception as e:
            raise RuntimeError("网络字节序转换成U32异常")
        return rt

    @staticmethod
    def ByteToString(vArrData):
        ByteString = ""
        for item in vArrData:
            ByteString += "{:02x}".format(item)
        return ByteString

    @staticmethod
    def ByteToStringOne(vArrData):
        ByteString = "{:02x}".format(vArrData)
        return ByteString

    @staticmethod
    def ByteToStringHigh(vArrData, offset, length):
        ByteString = ""
        if (offset + length) > len(vArrData):
            length = len(vArrData) - offset
        for i in range(offset,offset + length):
            ByteString += "{:02x}".format(vArrData[i])
        return ByteString

    @staticmethod
    def bytesToShort(b,offset):
        return int((b[offset + 1] & 0xff) | (b[offset] & 0xff) << 8)

    @staticmethod
    def stringToHexString(s):
        str = ""
        for i in range(0,len(s)):
            ch = int(s.charAt(i))
            s4 = hex(ch)[2:]
            str = str + s4
        return str

    @staticmethod
    def Bytes2String4(abyte0,i,j,s):
        if abyte0 is None or i < 0 or j <= 0 or  i + j > len(abyte0):
            return None
        stringbuffer = ""
        for k in range(0,j):
            s1 = hex(abyte0[k + i] & 255)[2:]
            if len(s1) == 1:
                s1 = "0" + s1
            stringbuffer += s1.upper()
            if s is not None:
                stringbuffer += s
        return stringbuffer

    @staticmethod
    def Bytes2String3(abyte0, s):
        if abyte0 is None:
            return None
        else:
            return Helper_String.Bytes2String4(abyte0, 0, len(abyte0), s)

    @staticmethod
    def Bytes2String2(abyte0, i, j):
        return Helper_String.Bytes2String4(abyte0, i, j, "")

    @staticmethod
    def Bytes2String(abyte0):
        return Helper_String.Bytes2String3(abyte0, "")

    @staticmethod
    def IsNullOrEmpty(str):
        if str is None or len(str) == 0:
            return True
        else:
            return False

    # 判断是否十六进制格式字符串
    @staticmethod
    def IsHex(strs):
        if Helper_String.IsNullOrEmpty(strs):
            return False
        PATTERN = "^[A-Fa-f0-9]+$"
        return re.match(PATTERN, strs)

    # 验证IP地址是否合法
    @staticmethod
    def IsIP(ip):
        if Helper_String.IsNullOrEmpty(ip):
            return False
        PATTERN = "(^((\\d|[01]?\\d\\d|2[0-4]\\d|25[0-5])\\.){3}(\\d|[01]?\\d\\d|2[0-4]\\d|25[0-5])$)|^(\\d|[1-2]\\d|3[0-2])$"
        return re.match(PATTERN, ip)

