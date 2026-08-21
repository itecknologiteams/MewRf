

# 设备信息
class Device_Model:
    def __init__(self):
        self._TerminalMAC = None
        self._MAC = None
        self._IP = None
        self._ServerPort = None
        self._RemoteIP = None
        self._RemotePort = None
        self._WorkingMode = None
        self._ConnectState = None
        self._DeviceType = None
        self._DHCP = None
        self._Mask = None
        self._Gateway = None
        self._IPv6 = None
        self._IPv6Getway = None
        self._CommType = None
        self._Reboot = None

    # 根据字符串，生成设备信息对象
    def Build(self,param):
        if param.startswith('^') and param.endswith('$'):
            param = param.lstrip('^').rstrip('$').upper()
            arrParam = param.split(',')
            for item in arrParam:
                keyValue = item.strip().split(':', 2)
                if len(keyValue) == 2:
                    if keyValue[0] == 'TERMINAL_MAC':
                        self._TerminalMAC = keyValue[1]
                    elif keyValue[0] == 'RFID_READER_INFORMATION':
                        self._DeviceType = keyValue[1]
                    elif keyValue[0] == 'IP':
                        self._IP = keyValue[1]
                    elif keyValue[0] == 'MASK':
                        self._Mask = keyValue[1]
                    elif keyValue[0] == 'GATEWAY':
                        self._Gateway = keyValue[1]
                    elif keyValue[0] == 'MAC':
                        self._MAC = keyValue[1].replace('-', ':')
                    elif keyValue[0] == 'PORT':
                        self._ServerPort = keyValue[1]
                    elif keyValue[0] == 'HOST_SERVER_IP':
                        self._RemoteIP = keyValue[1]
                    elif keyValue[0] == 'HOST_SERVER_PORT':
                        self._RemotePort = keyValue[1]
                    elif keyValue[0] == 'MODE':
                        self._WorkingMode = keyValue[1]
                    elif keyValue[0] == 'NET_STATE':
                        self._ConnectState = keyValue[1]
                    elif keyValue[0] == 'DHCP_SW':
                        self._DHCP = keyValue[1]
                    elif keyValue[0] == 'COMM_TYPE':
                        self._CommType = keyValue[1]
                    elif keyValue[0] == 'REBOOT':
                        self._Reboot = keyValue[1]
                    elif keyValue[0] == 'IPV6':
                        self._IPv6 = keyValue[1]
                    elif keyValue[0] == 'IPV6GATEWAY':
                        self._IPv6Getway = keyValue[1]
