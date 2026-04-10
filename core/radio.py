import asyncio
import os
import hashlib
import glob
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
        self.history_ptr: int = 0
        
        # UI State
        self.language: str = config.default_language
        self.is_compact: bool = (config.default_ui_mode == "compact")
        self.show_queue: bool = False
        
        # Modes
        self.loop_mode: bool = False
        self.loop_queue_mode: bool = False
        
        # Progress Tracking
        self.track_start_time: Optional[float] = None
        self.track_start_offset: float = 0.0
        self.seek_position: Optional[float] = None
        self.is_seeking: bool = False
        
        # Internal control
        self.action_queue = asyncio.Queue()
        self.last_user: Optional[discord.Member | discord.User] = None
        self.task: Optional[asyncio.Task] = None
        
        # Audio Cache
        self.cache_dir = os.path.join(os.getcwd(), "data", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._download_lock = asyncio.Lock()

        # Callbacks (to be set by UI/Player)
        self.on_state_change: Optional[Callable] = None
        self.on_download_complete: Optional[Callable] = None

    @property
    def history(self) -> List[Song]:
        return self.history_manager.history

    def dispatch(self, action: RadioAction, data: Any = None, user: Optional[discord.Member | discord.User] = None):
        user_str = f" by {user.name}" if user else " (System/Auto)"
        data_str = f" with [{data}]" if data is not None else ""
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
                log.info(f"[CACHE] Hit for: {query}")
                
                # Check for physical file existence
                if cached.get("local_path") and os.path.exists(cached["local_path"]):
                    song.is_resolving = False
                else:
                    song.is_resolving = True
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
                
                # Check cache for existing local files
                cached = self.db.get_cache(song.path)
                
                # Cache individual tracks from playlist
                self.db.set_cache(
                    url=song.path,
                    title=song.title,
                    uploader=song.uploader or "Unknown",
                    duration=song.duration,
                    thumbnail_url=song.thumbnail_url or "",
                    local_path=cached.get("local_path") if cached else None
                )
            
            if self.on_state_change:
                await self.on_state_change(self.current_song)
        else:
            log.warning(f"[RESOLVER] Failed to resolve playlist: {url}")

    async def _resolve_link_task(self, song: Song):
        try:
            resolved = await resolve_any(song.path, self.providers)
            if resolved:
                song.update(resolved)
                
                # Check if already cached
                cached = self.db.get_cache(song.path)
                
                # Save to cache
                self.db.set_cache(
                    url=song.path, # Use original link or webpage_url? webpage_url is better if available
                    title=song.title,
                    uploader=song.uploader or "Unknown",
                    duration=song.duration,
                    thumbnail_url=song.thumbnail_url or "",
                    local_path=cached.get("local_path") if cached else None
                )
                log.info(f"[RESOLVER] Successfully resolved: {song.uploader} - {song.title}")
            else:
                from ui_translate import t
                song.title = f"⚠️ {t('error_resolve')} {song.path}"
                log.warning(f"[RESOLVER] Failed to resolve link: {song.path}")
        except Exception as e:
            log.error(f"[RADIO] Resolution task exception: {e}")
        finally:
            song.is_resolving = False
            if self.on_state_change:
                await self.on_state_change(self.current_song)

    # --- Caching logic ---
    def get_cache_path(self, song: Song) -> Optional[str]:
        # Use filename-safe hash of the original URL/Path
        fn_hash = hashlib.sha1(song.path.encode()).hexdigest()
        
        # Look for any extension
        matches = glob.glob(os.path.join(self.cache_dir, f"{fn_hash}.*"))
        if matches:
            return matches[0]
            
        return None

    def is_cached(self, song: Song) -> bool:
        """Returns True if a valid local file exists for this song."""
        if not song or not song.path: return False
        
        # Check DB first for stored local path
        cached_data = self.db.get_cache(song.path)
        if cached_data:
            # Update song metadata from cache if it's currently a placeholder
            if song.title == song.path or "[" in song.title: 
                song.title = cached_data.get("title", song.title)
                song.uploader = cached_data.get("uploader", song.uploader)
                song.duration = cached_data.get("duration", song.duration)
                song.thumbnail_url = cached_data.get("thumbnail_url", song.thumbnail_url)

            if cached_data.get("local_path"):
                lp = cached_data["local_path"]
                if os.path.exists(lp): return True
            
        # Fallback: Check deterministic path with any extension
        lp = self.get_cache_path(song)
        if lp and os.path.exists(lp):
            # Update DB while we're at it
            self.db.set_cache(
                url=song.path,
                title=song.title,
                uploader=song.uploader or "Unknown",
                duration=song.duration,
                thumbnail_url=song.thumbnail_url or "",
                local_path=lp
            )
            return True
            
        return False

    async def start_cache_download(self, song: Song):
        """Initiates a background download of the song to the local cache."""
        if self.is_cached(song):
            return
            
        asyncio.create_task(self._download_task(song))

    async def _download_task(self, song: Song):
        # Prevent multiple downloads of the same song
        async with self._download_lock:
            if self.is_cached(song): return
            
            fn_hash = hashlib.sha1(song.path.encode()).hexdigest()
            target_path_template = os.path.join(self.cache_dir, f"{fn_hash}.%(ext)s")
            log.info(f"[CACHE] Starting download: {song.title}")
            
            try:
                # Use yt-dlp to download the best audio format
                cmd = [
                    self.config.ytdlp_path,
                    "-f", "bestaudio/best",
                    "--no-playlist",
                    "-o", target_path_template,
                    song.path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    # Find the actual file downloaded (since extension could be anything)
                    actual_path = self.get_cache_path(song)
                    if actual_path:
                        log.info(f"[CACHE] Download complete: {song.title} -> {actual_path}")
                        # Update DB with local path
                        self.db.set_cache(
                            url=song.path,
                            title=song.title,
                            uploader=song.uploader or "Unknown",
                            duration=song.duration,
                            thumbnail_url=song.thumbnail_url or "",
                            local_path=actual_path
                        )
                else:
                    err = stderr.decode().strip()
                    log.error(f"[CACHE] Download failed for {song.title}: {err}")
            except Exception as e:
                log.error(f"[CACHE] Download exception for {song.title}: {e}")

    def cleanup_cache(self):
        """Auto-cleanup of the cache based on size and expiry."""
        try:
            import time
            files = []
            for f in os.listdir(self.cache_dir):
                path = os.path.join(self.cache_dir, f)
                if os.path.isfile(path):
                    stats = os.stat(path)
                    files.append({
                        "path": path,
                        "size": stats.st_size,
                        "atime": stats.st_atime
                    })
            
            if not files: return
            
            # Sort by access time (oldest first)
            files.sort(key=lambda x: x["atime"])
            
            now = time.time()
            expiry_seconds = self.config.cache_expiry_days * 86400
            size_limit = self.config.max_cache_size_mb * 1024 * 1024
            
            total_size = sum(f["size"] for f in files)
            deleted_count = 0
            
            # 1. Expiry cleanup
            # Create a copy of files to iterate over, as we're modifying the original list
            files_to_check = list(files) 
            for f in files_to_check:
                if (now - f["atime"]) > expiry_seconds:
                    try:
                        os.remove(f["path"])
                        total_size -= f["size"]
                        files.remove(f) # Remove from the original list
                        deleted_count += 1
                    except Exception as e: 
                        log.warning(f"[CACHE] Could not delete expired file {f['path']}: {e}")
            
            # 2. Size cleanup (LRU)
            # Iterate over the remaining files (which are still sorted by access time)
            for f in files:
                if total_size <= size_limit:
                    break
                try:
                    os.remove(f["path"])
                    total_size -= f["size"]
                    deleted_count += 1
                except Exception as e: 
                    log.warning(f"[CACHE] Could not delete LRU file {f['path']}: {e}")
            
            if deleted_count > 0:
                log.info(f"[CACHE] Auto-cleanup: {deleted_count} files removed.")
                
        except Exception as e:
            log.error(f"[CACHE] Auto-cleanup error: {e}")

    def clear_cache(self):
        """Deletes all files in the cache directory."""
        try:
            count = 0
            for f in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
            
            # Reset local_path in DB
            self.db.clear_cache()
                
            log.info(f"[CACHE] Manual cache clear: {count} files removed.")
            return count
        except Exception as e:
            log.error(f"[CACHE] Error clearing cache: {e}")
            return 0

    def delete_cache_file(self, song: Song):
        """Deletes the local cache file for a specific song."""
        if not song or not song.path: return
        
        path = self.get_cache_path(song)
        if path and os.path.exists(path):
            try:
                os.remove(path)
                log.info(f"[CACHE] Ephemeral deletion: {song.title}")
                # Reset local_path in DB
                self.db.set_cache(
                    url=song.path,
                    title=song.title,
                    uploader=song.uploader or "Unknown",
                    duration=song.duration,
                    thumbnail_url=song.thumbnail_url or "",
                    local_path=None
                )
            except Exception as e:
                log.warning(f"[CACHE] Could not delete ephemeral file {path}: {e}")

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
