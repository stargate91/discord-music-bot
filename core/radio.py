import asyncio
import discord
from typing import List, Dict, Optional, Any, Callable
from radio_actions import RadioState as RadioStatusEnum, RadioAction
from embed_state import EmbedStateManager
from providers import get_providers, resolve_any, resolve_playlist_any
from core.models import Song
from core.favorites import FavoriteManager
from core.history import HistoryManager
from ui_theme import Theme
from logger import log

class RadioManager:
    """
    Central manager for the radio state and logic.
    Decoupled from specific Discord View implementations.
    """
    def __init__(self, config):
        self.config = config
        self.embed_manager = EmbedStateManager()
        self.providers = get_providers(config)
        self.fav_manager = FavoriteManager()
        self.history_manager = HistoryManager()
        
        # Initialize Theme
        Theme.init_theme(config)
        
        # Connection State
        self.voice: Optional[discord.VoiceClient] = None
        self.voice_channel_id: Optional[int] = None
        
        # Playback State
        self.status = RadioStatusEnum.IDLE
        self.current_song: Optional[Song] = None
        self.queue: List[Song] = []
        self.history = self.history_manager.history
        self.volume: float = config.default_volume
        self.station_message: Optional[discord.Message] = None
        self.now_playing_message: Optional[discord.Message] = None
        
        # UI State
        self.language: str = config.default_language
        self.is_compact: bool = (config.default_ui_mode == "compact")
        self.show_queue: bool = False
        
        # Progress Tracking
        self.track_start_time: Optional[float] = None
        self.track_start_offset: float = 0.0
        self.seek_position: Optional[float] = None
        self.is_seeking: bool = False
        
        # Internal control
        self.action_queue = asyncio.Queue()
        self.last_user: Optional[discord.Member | discord.User] = None
        self.task: Optional[asyncio.Task] = None

        # Callbacks (to be set by UI/Player)
        self.on_state_change: Optional[Callable] = None

    def dispatch(self, action: RadioAction, data: Any = None, user: Optional[discord.Member | discord.User] = None):
        """Dispatches an action to the player engine."""
        user_str = f" by {user.name}" if user else ""
        data_str = f" with [{data}]" if data else ""
        log.info(f"[ACTION] {action.name}{data_str}{user_str}")
        if user:
            self.last_user = user
        self.action_queue.put_nowait((action, data))
    async def add_external_link(self, url: str):
        """Adds an external link or playlist to the queue."""
        # Check if it's a playlist
        is_playlist = any(p.matches(url) and p.is_playlist(url) for p in self.providers)
        
        if is_playlist:
            log.info(f"[QUEUE] Playlist detected, starting batch resolution: {url}")
            asyncio.create_task(self._resolve_playlist_task(url))
            return None
            
        # Create a placeholder for single track using Song dataclass
        title_placeholder = url.split('?')[0].split('/')[-1] or url
        song = Song(
            title=title_placeholder,
            path=url,
            uploader="...",
            is_external=True,
            is_resolving=True
        )
        self.queue.append(song)
        log.info(f"[QUEUE] New link added: {url}")
        
        # Start resolution in background
        asyncio.create_task(self._resolve_link_task(song))
        return song

    async def _resolve_playlist_task(self, url: str):
        tracks_data = await resolve_playlist_any(url, self.providers)
        if tracks_data:
            log.info(f"[RESOLVER] Playlist resolved: {len(tracks_data)} tracks found.")
            for data in tracks_data:
                song = Song.from_dict(data)
                song.is_resolving = False
                self.queue.append(song)
            
            if self.on_state_change:
                await self.on_state_change(self.current_song)
        else:
            log.warning(f"[RESOLVER] Failed to resolve playlist: {url}")

    async def _resolve_link_task(self, song: Song):
        resolved = await resolve_any(song.path, self.providers)
        if resolved:
            song.update(resolved)
            log.info(f"[RESOLVER] Successfully resolved: {song.artist} - {song.title}")
        else:
            song.title = f"⚠️ Could not resolve: {song.path}"
            log.warning(f"[RESOLVER] Failed to resolve link: {song.path}")
        
        song.is_resolving = False
        if self.on_state_change:
            await self.on_state_change(self.current_song)

    def is_admin(self, user: discord.Member | discord.User) -> bool:
        if not isinstance(user, discord.Member):
            return False
        
        if user.guild_permissions.administrator:
            return True

        if user.id == user.guild.owner_id:
            return True

        user_role_ids = [role.id for role in user.roles]
        if self.config.admin_role_id > 0 and self.config.admin_role_id in user_role_ids:
            return True
        if self.config.sysadmin_role_id > 0 and self.config.sysadmin_role_id in user_role_ids:
            return True
        
        return False
