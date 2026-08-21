from abc import ABCMeta, abstractmethod

class ISearchDevice:
    __metaclass__ = ABCMeta  # 指定这是一个抽象类  

    '''
    设备信息回调
    '''
    @abstractmethod
    def DeviceInfo(self,model):
        pass

    '''
    调试信息
    '''
    @abstractmethod
    def DebugMsg(self,msg):
        pass
