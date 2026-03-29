import discord

class Icons:
    ADD: discord.PartialEmoji = None
    BACK: discord.PartialEmoji = None
    GEAR: discord.PartialEmoji = None
    CLOSE: discord.PartialEmoji = None
    DISCONNECT: discord.PartialEmoji = None
    FOLDER_HEART: discord.PartialEmoji = None
    GLOBE: discord.PartialEmoji = None
    HEADPHONES: discord.PartialEmoji = None
    HEART_MINUS: discord.PartialEmoji = None
    HEART_PLUS: discord.PartialEmoji = None
    HELP: discord.PartialEmoji = None
    HISTORY: discord.PartialEmoji = None
    IDLE: discord.PartialEmoji = None
    MOVE_DOWN: discord.PartialEmoji = None
    MOVE_UP: discord.PartialEmoji = None
    NEXT: discord.PartialEmoji = None
    PAUSE: discord.PartialEmoji = None
    PLAY: discord.PartialEmoji = None
    PREV: discord.PartialEmoji = None
    QUEUE: discord.PartialEmoji = None
    RADIO: discord.PartialEmoji = None
    REMOVE: discord.PartialEmoji = None
    SEARCH: discord.PartialEmoji = None
    SEEK: discord.PartialEmoji = None
    SKIP: discord.PartialEmoji = None
    STANDBY: discord.PartialEmoji = None
    STATUS: discord.PartialEmoji = None
    STOP: discord.PartialEmoji = None
    SWEEP: discord.PartialEmoji = None
    SYNC: discord.PartialEmoji = None
    VOLUME: discord.PartialEmoji = None
    WARNING: discord.PartialEmoji = None
    BUFFERING: discord.PartialEmoji = None
    REPEAT: discord.PartialEmoji = None
    
    PB_START: discord.PartialEmoji = None
    PB_LEFT: discord.PartialEmoji = None
    PB_FULL: discord.PartialEmoji = None
    PB_KNOB: discord.PartialEmoji = None
    PB_EMPTY: discord.PartialEmoji = None
    PB_RIGHT: discord.PartialEmoji = None
    PB_END: discord.PartialEmoji = None

    @classmethod
    def setup(cls, config):
        """Initializes all icons from config or defaults."""
        icons_data = config.emojis if hasattr(config, "emojis") else {}
        
        def get(name, default="❓"):
            val = icons_data.get(name, default)
            return discord.PartialEmoji.from_str(val)

        # Core Icons
        cls.ADD = get("ADD")
        cls.BACK = get("BACK")
        cls.GEAR = get("GEAR")
        cls.CLOSE = get("CLOSE")
        cls.DISCONNECT = get("DISCONNECT")
        cls.FOLDER_HEART = get("FOLDER_HEART")
        cls.GLOBE = get("GLOBE")
        cls.HEADPHONES = get("HEADPHONES")
        cls.HEART_MINUS = get("HEART_MINUS")
        cls.HEART_PLUS = get("HEART_PLUS")
        cls.HELP = get("HELP")
        cls.HISTORY = get("HISTORY")
        cls.IDLE = get("IDLE")
        cls.MOVE_DOWN = get("MOVE_DOWN")
        cls.MOVE_UP = get("MOVE_UP")
        cls.NEXT = get("NEXT")
        cls.PAUSE = get("PAUSE")
        cls.PLAY = get("PLAY")
        cls.PREV = get("PREV")
        cls.QUEUE = get("QUEUE")
        cls.RADIO = get("RADIO")
        cls.REMOVE = get("REMOVE")
        cls.SEARCH = get("SEARCH")
        cls.SEEK = get("SEEK")
        cls.SKIP = get("SKIP")
        cls.STANDBY = get("STANDBY")
        cls.STATUS = get("STATUS")
        cls.STOP = get("STOP")
        cls.SWEEP = get("SWEEP")
        cls.SYNC = get("SYNC")
        cls.VOLUME = get("VOLUME")
        cls.WARNING = get("WARNING")
        cls.REPEAT = get("REPEAT")
        cls.BUFFERING = get("BUFFERING")
        
        # PB Icons - Minimal ASCII fallback
        cls.PB_START = get("PB_START", "[")
        cls.PB_LEFT = get("PB_LEFT", "=")
        cls.PB_FULL = get("PB_FULL", "=")
        cls.PB_KNOB = get("PB_KNOB", ">")
        cls.PB_EMPTY = get("PB_EMPTY", "·")
        cls.PB_RIGHT = get("PB_RIGHT", "]")
        cls.PB_END = get("PB_END", "]")




# Default initialization
class DefaultConfig: emojis = {}
Icons.setup(DefaultConfig())
