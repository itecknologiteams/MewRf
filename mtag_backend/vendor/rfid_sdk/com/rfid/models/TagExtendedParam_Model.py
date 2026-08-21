#   标签扩展实体类
class TagExtendedParam_Model:
    def __init__(self,*data):
        self.IMJ_Tag_Focus = None
        self.IMJ_Fast_Id = None
        self.NXP_Fast_ID = None
        if data:
            self.IMJ_Tag_Focus = data[0]
            self.IMJ_Fast_Id = data[1]
            self.NXP_Fast_ID  = data[2]

