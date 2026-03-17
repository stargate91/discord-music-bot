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
    def list_max_title_len(self): return self.ui_settings.get("list_max_title_len", 60)
    @property
    def max_uploader_len(self): return self.ui_settings.get("max_uploader_len", 35)

def load_config(config_file: str = "config.json", instance_name: str = ""):
    config_dir = os.path.join(os.path.dirname(__file__), "configs")
    
    # env file logic: check configs/ directory first
    env_name = f".env.{instance_name}" if instance_name else ".env"
    env_path = os.path.join(config_dir, env_name)
    
    # Fallback to root for backwards compatibility if not found in configs/
    if not os.path.exists(env_path):
        root_env = os.path.join(os.path.dirname(__file__), env_name)
        if os.path.exists(root_env):
            env_path = root_env

    load_dotenv(env_path, override=True)
    
    # config file logic
    if os.path.isabs(config_file):
        base_path = config_file
    else:
        # Check in configs/ folder first
        base_path = os.path.join(config_dir, config_file)
        # Fallback to current folder if it doesn't exist in configs but exists here
        if not os.path.exists(base_path):
            fallback_path = os.path.join(os.path.dirname(__file__), config_file)
            if os.path.exists(fallback_path):
                base_path = fallback_path

    # Load configuration
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Configuration file not found: {base_path}")
        
    with open(base_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    token = os.getenv("DISCORD_TOKEN") or data.get("token")
    guild_id_raw = os.getenv("GUILD_ID") or data.get("guild_id", 0)
    guild_id = int(guild_id_raw) if guild_id_raw else 0

    # Environment overrides for channel IDs
    radio_channel_raw = os.getenv("RADIO_CHANNEL_ID") or data.get("radio_text_channel_id", 0)
    radio_channel_id = int(radio_channel_raw) if radio_channel_raw else 0
    
    autojoin_channel_raw = os.getenv("AUTO_JOIN_ID") or data.get("auto_join_channel_id", 0)
    auto_join_channel_id = int(autojoin_channel_raw) if autojoin_channel_raw else 0
    
    return Config(
        token=token,
        guild_id=guild_id,
        radio_text_channel_id=radio_channel_id,
        auto_join_channel_id=auto_join_channel_id,
        afk_channel_id=int(data.get("afk_channel_id", 0)),
        admin_role_id=int(data.get("admin_role_id", 0)),
        sysadmin_role_id=int(data.get("sysadmin_role_id", 0)),
        default_language=data.get("default_language", "hu"),
        default_ui_mode=data.get("default_ui_mode", "full"),
        ffmpeg_path=data.get("ffmpeg_path", "ffmpeg"),
        ytdlp_path=data.get("ytdlp_path", "yt-dlp"),
        languages=data.get("languages", []),
        ui_settings=data.get("ui_settings", {}),
        timings=data.get("timings", {}),
        defaults=data.get("defaults", {})
    )
