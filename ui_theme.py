import discord

class Theme:
    PRIMARY = 0x2b2d31
    SECONDARY = 0x2b2d31
    SUCCESS = 0x57F287
    WARNING = 0xFEE75C
    DANGER = 0xED4245
    BACKGROUND = 0x2b2d31
    ACCENT = 0xEB459E
    PLAYING = 0x1c6bff
    PAUSED = 0xFEE75C
    STOPPED = 0xED4245
    IDLE = 0x2b2d31
    BUFFERING = 0xEB459E

    @classmethod
    def init_theme(cls, config):
        theme_data = config.ui_settings.get("theme", {})
        cls.PRIMARY = int(theme_data.get("primary", "0x2b2d31"), 16)
        cls.SECONDARY = int(theme_data.get("secondary", "0x2b2d31"), 16)
        cls.SUCCESS = int(theme_data.get("success", "0x57F287"), 16)
        cls.WARNING = int(theme_data.get("warning", "0xFEE75C"), 16)
        cls.DANGER = int(theme_data.get("danger", "0xED4245"), 16)
        cls.BACKGROUND = int(theme_data.get("background", "0x2b2d31"), 16)
        cls.ACCENT = int(theme_data.get("accent", "0xEB459E"), 16)
        cls.PLAYING = int(theme_data.get("playing", "0x1c6bff"), 16)
        cls.PAUSED = int(theme_data.get("paused", "0xFEE75C"), 16)
        cls.STOPPED = int(theme_data.get("stopped", "0xED4245"), 16)
        cls.IDLE = int(theme_data.get("idle", "0x2b2d31"), 16)
        cls.BUFFERING = int(theme_data.get("buffering", "0xEB459E"), 16)
