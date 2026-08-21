
# GPO状态/电平操作
from com.rfid.enumeration.EGPIO import EGPIO


class ReaderGPOState_Model:
    def __init__(self,data):
        self.dicState = data

    # 生成电平操作集合
    def GPOAllConfig(egpoState,*GPONum):
        try:
            readerGPOState = ReaderGPOState_Model()
            stateHash = {}
            for i in GPONum:
                stateHash[i] = egpoState
            readerGPOState.dicState = stateHash
            return readerGPOState
        except Exception as e:
            print("方法GPOAllConfig失败，错误信息%s" % e)
            return None