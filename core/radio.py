import asyncio
import discord
from typing import List, Dict, Optional, Any, Callable
from radio_actions import RadioState as RadioStatusEnum, RadioAction
from embed_state import EmbedStateManager
from providers import get_providers, resolve_any, resolve_playlist_any
from .models import Song
from .favorites import FavoriteManager
from .history import HistoryManager
from .database import Database
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
        
        # Central Database
        self.db = Database(config.database_path)
        
        self.fav_manager = FavoriteManager(self.db)
        self.history_manager = HistoryManager(self.db, max_size=config.history_limit)
        
        # Initialize Theme
        Theme.init_theme(config)
        
        # Connection State
        self.voice: Optional[discord.VoiceClient] = None
        self.voice_channel_id: Optional[int] = None
        
        # Playback State
        self.status = RadioStatusEnum.IDLE
        self.current_song: Optional[Song] = None
        self.queue: List[Song] = []
        self.volume: float = config.default_volume
        self.station_message: Optional[discord.Message] = None
        self.now_playing_message: Optional[discord.Message] = None
        
        # Navigation State (Browser-like History)
        self.future_queue: List[Song] = []
        self.is_navigating: bool = False
        
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

    @property
    def history(self) -> List[Song]:
        return self.history_manager.history

    def dispatch(self, action: RadioAction, data: Any = None, user: Optional[discord.Member | discord.User] = None):
        user_str = f" by {user.name}" if user else ""
        data_str = f" with [{data}]" if data else ""
        log.info(f"[ACTION] {action.name}{data_str}{user_str}")
        if user:
            self.last_user = user
        self.action_queue.put_nowait((action, data))
    async def add_external_link(self, query: str, user: Optional[discord.Member | discord.User] = None):
        query = query.strip()
        
        # Check if it's a direct URL
        provider = next((p for p in self.providers if p.matches(query)), None)
        
        if provider:
            # It's a URL
            if provider.is_playlist(query):
                log.info(f"[QUEUE] Playlist detected: {query}")
                asyncio.create_task(self._resolve_playlist_task(query, user))
                return None
            
            # Single link - Check cache
            cached = self.db.get_cache(query)
            if cached:
                song = Song.from_dict(cached)
                song.path = query
                song.is_resolving = True
                song.is_external = True
                log.info(f"[CACHE] Hit for: {query}")
            else:
                from ui_translate import t
                song = Song(
                    title=t("resolving_link"),
                    path=query,
                    uploader="...",
                    duration=0,
                    is_external=True,
                    is_resolving=True
                )
        else:
            # It's a search query
            log.info(f"[SEARCH] Searching for: {query}")
            search_results = []
            for p in self.providers:
                if hasattr(p, 'search'):
                    res = await p.search(query, limit=1)
                    if res:
                        search_results.extend(res)
            
            if not search_results:
                log.warning(f"[SEARCH] No results found for: {query}")
                # We could send a message back here, but add_external_link is called from dispatch
                return None
            
            # Take the first result
            data = search_results[0]
            song = Song.from_dict(data)
            song.is_resolving = False # Search results are already somewhat resolved
        
        if user:
            song.user_id = str(user.id)
            song.requested_by = user.display_name
            
        self.queue.append(song)
        if not provider:
            log.info(f"[SEARCH] Added first result: {song.title}")
        else:
            log.info(f"[QUEUE] Added link: {query}")
        
        # Start resolution if needed (for direct links or refreshing search results)
        if provider or song.is_resolving:
            asyncio.create_task(self._resolve_link_task(song))
            
        return song

    async def add_songs(self, songs: List[Song], user: Optional[discord.Member | discord.User] = None):
        for song in songs:
            # Create a clean copy if needed (e.g. they might be from history)
            # but usually for favorites we just want them as is
            if user:
                song.requested_by = user.display_name
                song.user_id = str(user.id)
            self.queue.append(song)
        
        log.info(f"[QUEUE] Added {len(songs)} songs to queue.")
        if self.on_state_change:
            await self.on_state_change(self.current_song)

    async def _resolve_playlist_task(self, url: str, user: Optional[discord.Member | discord.User] = None):
        tracks_data = await resolve_playlist_any(url, self.providers)
        if tracks_data:
            log.info(f"[RESOLVER] Playlist resolved: {len(tracks_data)} tracks found.")
            for data in tracks_data:
                song = Song.from_dict(data)
                song.is_resolving = False
                if user:
                    song.user_id = str(user.id)
                    song.requested_by = user.display_name
                self.queue.append(song)
                
                # Cache individual tracks from playlist
                self.db.set_cache(
                    url=song.path,
                    title=song.title,
                    uploader=song.uploader or "Unknown",
                    duration=song.duration,
                    thumbnail_url=song.thumbnail_url or ""
                )
            
            if self.on_state_change:
                await self.on_state_change(self.current_song)
        else:
            log.warning(f"[RESOLVER] Failed to resolve playlist: {url}")

    async def _resolve_link_task(self, song: Song):
        resolved = await resolve_any(song.path, self.providers)
        if resolved:
            song.update(resolved)
            # Save to cache
            self.db.set_cache(
                url=song.path, # Use original link or webpage_url? webpage_url is better if available
                title=song.title,
                uploader=song.uploader or "Unknown",
                duration=song.duration,
                thumbnail_url=song.thumbnail_url or ""
            )
            log.info(f"[RESOLVER] Successfully resolved: {song.uploader} - {song.title}")
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

    def can_interact(self, user: discord.Member | discord.User) -> bool:
        """
        Checks if the user has permission to interact with the bot.
        Admins can always interact.
        The voice channel restriction ONLY applies if the bot is:
        - PLAYING
        - PAUSED
        - STOPPED
        If the bot is IDLE, anyone can interact (e.g. to make it join their channel).
        """
        if self.is_admin(user):
            return True

        # If IDLE, we don't restrict by channel
        if self.status == RadioStatusEnum.IDLE:
            return True

        if not self.voice or not self.voice.channel:
            # If not in voice despite status (shouldn't happen often), allow interaction
            return True

        if not isinstance(user, discord.Member):
            return False

        # Must be in the same voice channel if the bot is active
        if not user.voice or user.voice.channel.id != self.voice.channel.id:
            return False

        return True
