from enum import Enum, auto

class RadioState(Enum):
    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    STOPPED = auto()

class RadioAction(Enum):
    JOIN = auto()
    DISCONNECT = auto()
    PLAY = auto()
    PAUSE = auto()
    STOP = auto()
    SKIP = auto()
    SEEK = auto()
    REPLAY = auto()
    SET_GENRE = auto()
    SET_VOLUME = auto()
    ADD_TO_QUEUE = auto()
    REMOVE_FROM_QUEUE = auto()
    CLEAR_QUEUE = auto()
    SHUFFLE = auto()
    BACK = auto()
    FORWARD = auto()
    SET_LANGUAGE = auto()
    ADD_EXT_LINK = auto()
    REFRESH_UI = auto()
