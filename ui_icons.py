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
        
        def get(name, default):
            return discord.PartialEmoji.from_str(icons_data.get(name, default))

        cls.GEAR = get("GEAR", "⚙️")
        cls.ADD = get("ADD", "<:plus:1478259626213638194>")
        cls.BACK = get("BACK", "<:skipback:1478346950423351409>")
        cls.CLOSE = get("CLOSE", "<:x_:1478346611057889341>")
        cls.DISCONNECT = get("DISCONNECT", "<:unplug:1478251603848069251>")
        cls.FOLDER_HEART = get("FOLDER_HEART", "<:folderheart:1478959293867757618>")
        cls.GLOBE = get("GLOBE", "<:globe:1479722340320542820>")
        cls.HEADPHONES = get("HEADPHONES", "<:headphones:1478347620526325842>")
        cls.HEART_MINUS = get("HEART_MINUS", "<:heartminus:1478958133526270143>")
        cls.HEART_PLUS = get("HEART_PLUS", "<:heartplus:1478958134981820496>")
        cls.HELP = get("HELP", "<:badgequestionmark:1483516990118166632>")
        cls.HISTORY = get("HISTORY", "<:scrolltext:1478347243428905061>")
        cls.IDLE = get("IDLE", "<:moon:1482978543196573746>")
        cls.MOVE_DOWN = get("MOVE_DOWN", "<:chevrondown:1478330165896675389>")
        cls.MOVE_UP = get("MOVE_UP", "<:chevronup:1478330154437836883>")
        cls.NEXT = get("NEXT", "<:chevronright:1478332976587604019>")
        cls.PAUSE = get("PAUSE", "<:pause:1478346796118970428>")
        cls.PLAY = get("PLAY", "<:play:1478346681824317490>")
        cls.PREV = get("PREV", "<:chevronleft:1478332975077785631>")
        cls.QUEUE = get("QUEUE", "<:rows3:1478347365923688543>")
        cls.RADIO = get("RADIO", "<:audiolines:1478347583934955540>")
        cls.REMOVE = get("REMOVE", "<:trash2:1478347449004458095>")
        cls.SEARCH = get("SEARCH", "<:search:1478333583797256292>")
        cls.SEEK = get("SEEK", "<:fastforward:1478347054182043678>")
        cls.SKIP = get("SKIP", "<:skipforward:1478346952222572597>")
        cls.STANDBY = get("STANDBY", "<a:trailloading:1478249295680503939>")
        cls.STATUS = get("STATUS", "<:folderopen:1478347534312276041>")
        cls.STOP = get("STOP", "<:square:1478346870945484913>")
        cls.SWEEP = get("SWEEP", "<:brushcleaning:1478347327361253426>")
        cls.SYNC = get("SYNC", "<a:musicplay:1478239850355228754>")
        cls.VOLUME = get("VOLUME", "<:volume2:1478347170959589468>")
        cls.WARNING = get("WARNING", "<:trianglealert:1478266385212641421>")
        cls.BUFFERING = get("BUFFERING", "<a:trailloading:1478249295680503939>")
        
        # PB Icons
        cls.PB_START = get("PB_START", "<:pbleftfullstart:1479349705011105915>")
        cls.PB_LEFT = get("PB_LEFT", "<:pbleftfull:1479349704016920656>")
        cls.PB_FULL = get("PB_FULL", "<:pbfull:1479349702880137437>")
        cls.PB_KNOB = get("PB_KNOB", "<:pbdivider:1479349699835072573>")
        cls.PB_EMPTY = get("PB_EMPTY", "<:pbempty:1479349701450137660>")
        cls.PB_RIGHT = get("PB_RIGHT", "<:pbrightempty:1479349706227191828>")
        cls.PB_END = get("PB_END", "<:pbrightemptyend:1479349707418636451>")

# Default initialization
class DefaultConfig: emojis = {}
Icons.setup(DefaultConfig())
