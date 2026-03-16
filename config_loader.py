import json
import os
from dotenv import load_dotenv
from dataclasses import dataclass, field

@dataclass
class Config:
    token: str
    guild_id: int
    radio_text_channel_id: int
    auto_join_channel_id: int
    afk_channel_id: int
    admin_role_id: int
    sysadmin_role_id: int
    default_language: str
    default_ui_mode: str
    default_presence: str
    ffmpeg_path: str
    ytdlp_path: str
    languages: list
    ui_settings: dict
    timings: dict
    defaults: dict

    @property
    def embed_refresh_minutes(self): return self.timings.get("embed_refresh_minutes", 58)
    @property
    def progress_update_seconds(self): return self.timings.get("progress_update_seconds", 15)
    @property
    def error_retry_seconds(self): return self.timings.get("error_retry_seconds", 5)
    @property
    def afk_timeout_seconds(self): return self.timings.get("afk_timeout_seconds", 300)
    @property
    def default_volume(self): return self.defaults.get("volume", 0.5)
    @property
    def progress_bar_width(self): return self.ui_settings.get("progress_bar_width", 18)
    @property
    def thumbnail_size(self): return self.ui_settings.get("thumbnail_size", 40)
    @property
    def max_title_len(self): return self.ui_settings.get("max_title_len", 45)
    @property
    def max_uploader_len(self): return self.ui_settings.get("max_uploader_len", 35)

def load_config():
    load_dotenv()
    base_dir = os.path.dirname(__file__)
    base_path = os.path.join(base_dir, "config.json")
    local_path = os.path.join(base_dir, "config.local.json")
    
    # Load base config
    with open(base_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Merge local config if exists
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            local_data = json.load(f)
            # Update root level keys, and nested dicts for ui_settings, timings, defaults
            for key, value in local_data.items():
                if isinstance(value, dict) and key in data and isinstance(data[key], dict):
                    data[key].update(value)
                else:
                    data[key] = value
    
    token = os.getenv("DISCORD_TOKEN") or data.get("token")
    guild_id_raw = os.getenv("GUILD_ID") or data.get("guild_id", 0)
    guild_id = int(guild_id_raw) if guild_id_raw else 0
    
    return Config(
        token=token,
        guild_id=guild_id,
        radio_text_channel_id=int(data.get("radio_text_channel_id", 0)),
        auto_join_channel_id=int(data.get("auto_join_channel_id", 0)),
        afk_channel_id=int(data.get("afk_channel_id", 0)),
        admin_role_id=int(data.get("admin_role_id", 0)),
        sysadmin_role_id=int(data.get("sysadmin_role_id", 0)),
        default_language=data.get("default_language", "hu"),
        default_ui_mode=data.get("default_ui_mode", "full"),
        default_presence=data.get("default_presence", "Waiting for links..."),
        ffmpeg_path=data.get("ffmpeg_path", "ffmpeg"),
        ytdlp_path=data.get("ytdlp_path", "yt-dlp"),
        languages=data.get("languages", []),
        ui_settings=data.get("ui_settings", {}),
        timings=data.get("timings", {}),
        defaults=data.get("defaults", {})
    )
