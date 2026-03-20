from enum import Enum, auto

class RadioState(Enum):
    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    STOPPED = auto()
    BUFFERING = auto()

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
    
    # Queue Management
    REMOVE_FROM_QUEUE = auto()
    CLEAR_QUEUE = auto()
    MOVE_SONG = auto() # Used for both UP/DOWN
    
    # Favorites & History
    TOGGLE_FAVORITE = auto()
    CLEAR_FAVORITES = auto()
    CLEAR_HISTORY = auto()
    
    # Modes
    LOOP = auto()
    LOOP_QUEUE = auto()
    SHUFFLE = auto()
    RESTART = auto()
    CLEAR_CACHE = auto()

