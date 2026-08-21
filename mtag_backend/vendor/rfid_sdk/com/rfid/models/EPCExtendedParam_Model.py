
# EPC扩展基带参数
from com.rfid.models.ASTExtendedParam2_Model import ASTExtendedParam2_Model
from com.rfid.models.ASTExtendedParam_Model import ASTExtendedParam_Model
from com.rfid.models.DNQExtendedParam_Model import DNQExtendedParam_Model
from com.rfid.models.LBTExtendedParam_Model import LBTExtendedParam_Model
from com.rfid.models.TagExtendedParam_Model import TagExtendedParam_Model


class EPCExtendedParam_Model:
    def __init__(self):
        # TAG扩展参数
        self.TagExtendedParam = TagExtendedParam_Model()
        # DNQ扩展参数
        self.DNQExtendedParam = DNQExtendedParam_Model()
        # AST扩展参数
        self.ASTExtendedParam = ASTExtendedParam_Model()
        # AST2扩展参数
        self.ASTExtendedParam2 = ASTExtendedParam2_Model()
        # LBT扩展参数
        self.LBTExtendedParam = LBTExtendedParam_Model()