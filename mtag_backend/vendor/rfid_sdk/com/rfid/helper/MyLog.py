
class MyLog:
    IsDebug = False

    @staticmethod
    def p(msg):
        if MyLog.IsDebug:
            print(msg)
