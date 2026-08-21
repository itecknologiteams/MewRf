import six

from com.rfid.helper.Helper_Protocol import Helper_Protocol
from com.rfid.helper.Helper_String import Helper_String
from com.rfid.protocol.ControlWord import ControlWord

# 数据帧基类，请参照协议查看属性含义  - RFID
class BaseFrame:

    def __init__(self, *datas):
        # 协议头，固定
        self._Head = 0xAA
        self._CW = None
        self._Serial_Mac = 0
        self._Data_Len = 0
        self._Data = None
        self._CRC = None
        self._CRCData = None
        self._FreamData = None
        self._IsErrorCommandResponse = False
        if datas:
            try:
                data = datas[0]
                # 保留整个数据帧
                self._FreamData = data
                # 用于CRC较验
                self._CRCData = bytearray(len(data) - 3)
                Helper_Protocol.arrayCopy(data, 1, self._CRCData, 0, len(self._CRCData))
                b_CW = bytearray(2)
                copyIndex = 1
                Helper_Protocol.arrayCopy(data, copyIndex, b_CW, 0, 2)
                copyIndex += 2
                self._CW = ControlWord().SetData(b_CW)
                if self._CW._CW_13 == '1':
                    self._Serial_Mac = data[copyIndex]
                    copyIndex += 1
                tempLen = bytearray(2)
                Helper_Protocol.arrayCopy(data, copyIndex, tempLen, 0, 2)
                Helper_Protocol.Reverse(tempLen)
                self._Data_Len = Helper_Protocol.U16BytesToInt(tempLen, 0)
                copyIndex += 2
                self._Data = bytearray(self._Data_Len)
                Helper_Protocol.arrayCopy(data, copyIndex, self._Data, 0, self._Data_Len)
                copyIndex += self._Data_Len
                self._CRC = bytearray(2)
                Helper_Protocol.arrayCopy(data, copyIndex, self._CRC, 0, 2)
            except Exception as e:
                print("失败，解包失败:%s" % e)

    # 读写器主动响应非法指令
    ERROR_DICTIONARY = {
        0: 'Error type',
        1: 'CRC error',
        2: 'error MID',
        3: 'control world error',
        4: 'state error',
        5: 'stack error',
        6: 'message parameter error',
        7: 'frame length error',
        8: 'other error'
    }

    # 封包
    def GetByteData(self, _Is585):
        rt = None
        try:
            putCount = 0
            list_rt = [0 for x in range(0, 1024)]
            list_rt.append(self._Head)
            putCount += 1
            list_rt.append(self._CW.GetBytes())
            putCount += 2
            if _Is585:
                list_rt.append(self._Serial_Mac)
                putCount += 1
            tempLen = Helper_Protocol.ReverseIntToU16Bytes(self._Data_Len)
            list_rt.append(tempLen)
            putCount += 2
            if self._Data:
                list_rt.append(self._Data)
                putCount += len(self._Data)
            bArray = [0 for x in range(0, putCount)]
            Helper_Protocol.arrayCopy(list_rt, 0, bArray, 0, len(bArray))
            rt = bArray
            self._CRCData = [0 for x in range(0, len(rt) - 1)]  # 用于CRC较验
            Helper_Protocol.arrayCopy(rt, 1, self._CRCData, 0, len(self._CRCData))
            self._CRC = Helper_Protocol.CRC16_8005(self._CRCData, len(self._CRCData))  # 得到CRC较验值
            list_rt.append(self._CRC)
            putCount += 2
            bArray = [0 for x in range(0, putCount)]
            Helper_Protocol.arrayCopy(list_rt, 0, bArray, 0, len(bArray))
            strRT = Helper_String.PrintHexStringByteSum(bArray)
            rt = bArray
        except Exception as e:
            print("失败，错误信息%s" % e)
        return rt

    # 判断数据帧是否有效
    def CheckCRC(self):
        try:
            if self._CRCData != None and self._CRC != None:
                tempCRC = Helper_Protocol.CRC16_8005(self._CRCData, len(self._CRCData))
                if Helper_Protocol.EqualsByteArray(tempCRC, self._CRC):
                    return True
        except Exception as e:
            print("失败，错误信息%s" % e)

    # 提供默认的返回值方法
    def GetReturnData(self):
        rt = ""
        try:
            rt = Helper_String.PrintHexStringByteSum(self._Data)
        except Exception as e:
            print("失败，错误信息%s" % e)
        return rt

    # 获得可选参数
    def GetOptionalParam(self, param):
        rt = {}
        try:
            arrParam = param.split('&')
            for i in range(0, len(arrParam)):
                item = arrParam[i].split(',')
                if len(item) == 2:
                    rt[int(item[0]) & 0xff] = Helper_String.hexStringToBytes(item[1])
        except Exception as e:
            print("失败，错误信息%s" % e)
        return rt

    # 获得帧数据
    # @param _Is585 是否是485通讯
    def GetFreamData(self, _Is585):
        rt = None
        try:
            list_rt = bytearray()
            list_rt.append(self._Head)
            list_rt.extend(Helper_String.BytesToArraylist(self._CW.GetBytes()))
            if _Is585:
                list_rt.append(self._Serial_Mac)
            tempLen = Helper_String.IntToBytes(self._Data_Len)
            tempLen = Helper_String.ArrayReverse(tempLen)
            list_rt.extend(Helper_String.BytesToArraylist(tempLen))

            if self._Data != None:
                list_rt.extend(Helper_String.BytesToArraylist(self._Data))
            rt = Helper_String.ArraylisttoBytes(list_rt)

            self._CRCData = bytearray(len(rt) - 1)  # 用于CRC较验
            Helper_Protocol.arrayCopy(rt, 1, self._CRCData, 0, len(self._CRCData))
            self._CRC = Helper_Protocol.CRC16_8005(self._CRCData, len(self._CRCData))  # 得到CRC较验值
            list_rt.extend(self._CRC)
            rt = Helper_String.ArraylisttoBytes(list_rt)
        except Exception as e:
            print("失败，错误信息%s" % e)
            raise Exception
        return rt
