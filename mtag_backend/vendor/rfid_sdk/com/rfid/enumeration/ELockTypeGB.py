from enum import Enum


class ELockTypeGB(Enum):
    Readable_Writable = 0x00
    ReadOnly = 0x01
    WriteOnly = 0x02
    Unreadable_Unwritable = 0x03
    Safemode_0x11 = 0x11
    Safemode_0x12 = 0x12
    Safemode_0x13 = 0x13