

class G2V2Authenticate_Model:
    def __init__(self,*data):
        self._AuthMethod = None  # TAM认证方法标识号
        self._CustomData = None  # TAM附加数据标志
        self._KeyID = None  # TAM
        self.KeyID = None
        self._Profile = None  # 数据区参数
        self._Offset = None  # 数据区起始区块位置
        self._BlockCount = None  # 数据块数目
        self._ProtMode = None  # 数据访问模式

        if data:
            self._AuthMethod = data[0]
            self._CustomData = data[1]
            self._KeyID = data[2]
            self._Profile = data[3]
            self._Offset = data[4]
            self._BlockCount = data[5]
            self._ProtMode = data[6]

