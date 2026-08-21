
class Helper_Byte:
    @staticmethod
    def byte2Short(b):
        shortValue = 0
        for i in range(0,len(b)):
            shortValue += (b[i] & 0xFF) << (8 * (1 - i))
        return shortValue
