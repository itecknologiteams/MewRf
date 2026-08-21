from com.rfid.enumeration.EReaderResult import EReaderResult

# Reader 网络配置
class ReaderNetwork_Model:
    def __init__(self,*data):
        self.Mac = None
        self.Ipv4Address = None
        self.Ipv4Mask = None
        self.Ipv4GateWay = None
        self.Ipv4Dns = None

        self.DhcpSwitch = False
        self.Ipv6Switch = False
        self.Ipv6Address = None
        self.Ipv6Mask = None
        self.Ipv6GateWay = None
        self.Ipv6Dns = None
        if len(data) == 3:
            self.Ipv4Address = data[0]
            self.Ipv4Mask = data[1]
            self.Ipv4GateWay = data[2]
        elif len(data) == 4:
            self.Ipv4Address = data[0]
            self.Ipv4Mask = data[1]
            self.Ipv4GateWay = data[2]
            self.Ipv4Dns = data[3]

    # 根据字符串获取ReaderNetWork对象
    def getReaderNetWork(self,param):
        if param is None or len(param) == 0:
            return EReaderResult.RT_FAILED_ERR

        ipParam = param.split('|')
        self.Ipv4Address = ipParam[0]
        self.Ipv4Mask = ipParam[1]
        self.Ipv4GateWay = ipParam[2]

        if len(ipParam) == 4:
            appendParam = ipParam[3].split('&')
            # ipv4Dns
            ipDns = appendParam[0].split(',')
            if int(ipDns[0]) == 0x00:
                self.Ipv4Dns = ''
            elif int(ipDns[0]) == 0x01:
                self.Ipv4Dns = ipDns[1]
            # 解析IPv6
            for i in range(0,len(appendParam)):
                strParam = appendParam[i].split(',')
                # 十六进制
                if int(strParam[0]) == 0x60: #96
                    if strParam[1] == "1":
                        self.Ipv6Switch = True
                    else:
                        self.Ipv6Switch = False
                elif int(strParam[0]) == 0x61:  # 97
                    self.Ipv6Address = strParam[1]
                elif int(strParam[0]) == 0x62:  # 98
                    self.Ipv6Mask = strParam[1]
                elif int(strParam[0]) == 0x63:  # 99
                    self.Ipv6GateWay = strParam[1]
                elif int(strParam[0]) == 0x64:  # 100
                    self.Ipv6Dns = strParam[1]
        return EReaderResult.RT_OK

    # 根据属性获取网络配置参数
    def getReaderNetWorkParam(self):
        param = ""
        try:
            param += self.Ipv4Address.strip() + "|"
            param += self.Ipv4Mask.strip() + "|"
            param += self.Ipv4GateWay.strip() + "|"
            if self.Ipv4Dns and len(self.Ipv4Dns) != 0:
                param += "1," + self.Ipv4Dns.strip() + "&"
            if self.Ipv6Switch != None and self.Ipv6Switch == True:
                ipv6 = ""
                if len(self.Ipv6Address) != 0 and  len(self.Ipv6Mask) != 0 and len(self.Ipv6GateWay) != 0 and  len(self.Ipv6Dns) != 0:
                    ipv6 = "96,1&97," + self.Ipv6Address + "&98," + self.Ipv6Mask + "&99," + self.Ipv6GateWay + "&100," + self.Ipv6Dns
                    param += ipv6
            param.rstrip('&')
            param.rstrip('|')
        except Exception as e:
            print("方法getReaderNetWorkParam失败，错误信息%s" % e)
            return ""
        return param
