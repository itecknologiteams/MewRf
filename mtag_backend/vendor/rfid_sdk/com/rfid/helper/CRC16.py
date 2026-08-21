
class CRC16:
    crcTable = [0 for x in range(0,256)]
    gPloy = 0x8005

    @staticmethod
    def getCrcOfByte(aByte):
        value = aByte << 8
        for count in range(7,0,-1):
            if (value & 0x8000) != 0: # 高第16位为1，可以按位异或
                value = (value << 1) ^ CRC16.gPloy
            else:
                value = value << 1 # 首位为0，左移
        value = value & 0xFFFF # 取低16位的值
        return int(value)

    # 生成0 - 255对应的CRC16校验码
    @staticmethod
    def computeCrcTable():
        for i in range(0,256):
            CRC16.crcTable[i] = CRC16.getCrcOfByte(i)