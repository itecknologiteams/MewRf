from enum import Enum


class ETriggerCode(Enum):
    Single_Antenna_read_EPC = 0
    Single_Antenna_read_EPC_and_TID = 1
    Double_Antenna_read_EPC = 2
    Double_Antenna_read_EPC_and_TID = 3
    Four_Antenna_read_EPC = 4
    Four_Antenna_read_EPC_and_TID = 5
    Eight_Antenna_read_EPC = 6
    Eight_Antenna_read_EPC_and_TID = 7
    Twelve_Antenna_read_EPC = 8
    Twelve_Antenna_read_EPC_and_TID = 9
    Twenty_four_Antenna_read_EPC = 10
    Twenty_four_Antenna_read_EPC_and_TID = 11
    Custom_Read_0 = 12
    Custom_Read_1 = 13
    Custom_Read_2 = 14