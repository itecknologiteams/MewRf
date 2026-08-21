from enum import Enum


class ETriggerStop(Enum):
    OFF = 0
    Low_level = 1
    High_level = 2
    Rising_edge = 3
    Falling_edge = 4
    Any_edge = 5
    Delay = 6