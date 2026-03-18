from enum import Enum, auto

class RadioState(Enum):
    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    STOPPED = auto()

class RadioAction(Enum):
    JOIN = auto()
    DISCONNECT = auto()
    PAUSE = auto()
    STOP = auto()
    SKIP = auto()
    SEEK = auto()
    REPLAY = auto()
    SET_VOLUME = auto()
    BACK = auto()
    ADD_EXT_LINK = auto()
    ADD_SONGS = auto()
