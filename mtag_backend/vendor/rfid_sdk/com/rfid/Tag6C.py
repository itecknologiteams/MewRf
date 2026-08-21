from com.rfid import RFIDReader
from com.rfid.enumeration.EAntennaNo import EAntennaNo


class Tag6C:

    #   为了扩展成24天线而新增的转换函数
    @staticmethod
    def ConvertToNewParam(oldParam,key):
        newParam = ""
        antNum = 0
        if key == None:
            key = "10"
        param = oldParam.rstrip("|").split("|")
        if len(param) >= 2:
            antNum = int(param[0])

            if antNum >= EAntennaNo._24.value:
                antNum -= EAntennaNo._24.value
            if antNum >= EAntennaNo._23.value and antNum < EAntennaNo._24.value:
                antNum -= EAntennaNo._23.value
            if antNum >= EAntennaNo._22.value and antNum < EAntennaNo._23.value:
                antNum -= EAntennaNo._22.value
            if antNum >= EAntennaNo._21.value and antNum < EAntennaNo._22.value:
                antNum -= EAntennaNo._21.value
            if antNum >= EAntennaNo._20.value and antNum < EAntennaNo._21.value:
                antNum -= EAntennaNo._20.value
            if antNum >= EAntennaNo._19.value and antNum < EAntennaNo._20.value:
                antNum -= EAntennaNo._19.value
            if antNum >= EAntennaNo._18.value and antNum < EAntennaNo._19.value:
                antNum -= EAntennaNo._18.value
            if antNum >= EAntennaNo._17.value and antNum < EAntennaNo._18.value:
                antNum -= EAntennaNo._17.value
            if antNum >= EAntennaNo._16.value and antNum < EAntennaNo._17.value:
                antNum -= EAntennaNo._16.value
            if antNum >= EAntennaNo._15.value and antNum < EAntennaNo._16.value:
                antNum -= EAntennaNo._15.value
            if antNum >= EAntennaNo._14.value and antNum < EAntennaNo._15.value:
                antNum -= EAntennaNo._14.value
            if antNum >= EAntennaNo._13.value and antNum < EAntennaNo._14.value:
                antNum -= EAntennaNo._13.value
            if antNum >= EAntennaNo._12.value and antNum < EAntennaNo._13.value:
                antNum -= EAntennaNo._12.value
            if antNum >= EAntennaNo._11.value and antNum < EAntennaNo._12.value:
                antNum -= EAntennaNo._11.value
            if antNum >= EAntennaNo._10.value and antNum < EAntennaNo._11.value:
                antNum -= EAntennaNo._10.value
            if antNum >= EAntennaNo._9.value and antNum < EAntennaNo._10.value:
                antNum -= EAntennaNo._9.value
            newParam += antNum + "|"
            exAntNum = (int(param[0]) - antNum) / 256
            for i in range(1,len(param)):
                newParam += param[i] + "|"
            newParam = newParam.rstrip('|')
            if exAntNum > 0:
                if param[len(param) - 1].__contains__(","):
                    newParam += "&" + key + "," + (hex(exAntNum)[2:]).rjust(4, '0')
                else:
                    newParam += "&" + key + "," + (hex(exAntNum)[2:]).rjust(4, '0')
            return newParam
        else:
            return oldParam

    @staticmethod
    def GetEPC(connID,antNo,readType):
        rt = -1
        try:
            readParam = antNo + "|" + readType.GetNum()
            rtStr = RFIDReader.Read_EPC(connID, Tag6C.ConvertToNewParam(readParam))
            rt = RFIDReader.GetReturnData(rtStr)
        except Exception as e:
            pass
        return rt




