import asyncio
import discord
from ui_translate import t, init_translate
from radio_actions import RadioState as RadioStatusEnum
from core.models import Song
from ui_player import WelcomeLayout, FrequencyStationView, NowPlayingView, init_player_ui
from ui_search import FullQueueView
from ui_utils import safe_delete_message, safe_fetch_message
from logger import log

class UIManager:
    def __init__(self, bot: discord.Client, config, radio):
        self.bot = bot
        self.config = config
        self.radio = radio
        self._ui_lock = asyncio.Lock()
        self._last_cleanup = 0.0
        
        # Initialize sub-systems
        init_translate(radio)
        init_player_ui(bot, config, self.update_now_playing)

    async def update_now_playing(self, song: Song | None, force_channel_id: int | None = None):
        """Public entry point for UI updates with locking."""
        async with self._ui_lock:
            await self._update_ui_internal(song, force_channel_id=force_channel_id)

    async def _update_ui_internal(self, song: Song | None, force_channel_id: int | None = None):
        """Internal UI rendering logic."""
        try:
            # Handle potential dict fallback from older code
            if isinstance(song, dict):
                song = None
                
            has_no_song = song is None or not song.path
            show_player = not has_no_song or self.radio.voice_channel_id
            
            if not self.bot or self.bot.is_closed(): return
            
            # 1. Presence & Channel Status Updates
            await self._update_presence(song)
            await self._update_channel_status(song, force_channel_id=force_channel_id)

            channel = self.bot.get_channel(self.config.radio_text_channel_id)
            if not channel:
                try: 
                    channel = await self.bot.fetch_channel(self.config.radio_text_channel_id)
                except Exception as e:
                    log.error(f"UI Manager could not find radio channel {self.config.radio_text_channel_id}: {e}")
                    return

            # 2. Handle Station Message (Header)
            await self._render_station_message(channel)

            # 3. Handle Player Message (Centerpiece)
            await self._render_player_message(channel, song, show_player)

            # 4. Aggressive Cleanup (now after rendering to ensure new IDs are saved)
            # Add a small delay to ensure Discord's cache is updated before we sweep history
            await asyncio.sleep(0.5) 
            await self._cleanup_stray_messages(channel, force=not show_player)

        except Exception as e:
            log.error(f"UIManager update failed: {e}")

    async def _update_presence(self, song: Song | None):
        try:
            if self.radio.status == RadioStatusEnum.PLAYING and song:
                # Use native Listening activity so Discord handles the "Listening to" prefix automatically
                activity = discord.Activity(
                    type=discord.ActivityType.listening,
                    name=song.title or t('unknown')
                )
                await self.bot.change_presence(activity=activity)
            else:
                # Elegant messages for Tatiana when not playing
                if self.radio.status == RadioStatusEnum.PAUSED:
                    msg = t('holding_rhythm')
                elif self.radio.status == RadioStatusEnum.IDLE:
                    msg = t('waiting_melody')
                else: # STOPPED or other
                    msg = t('at_command')
                
                await self.bot.change_presence(activity=discord.Game(name=msg))
        except Exception as e:
            log.debug(f"Presence update failed: {e}")

    async def _update_channel_status(self, song: Song | None, force_channel_id: int | None = None):
        """Updates the Voice Channel's status text (if enabled)."""
        if not self.config.update_voice_status:
            return
            
        try:
            target_id = force_channel_id or self.radio.voice_channel_id
            if not target_id:
                return
                
            channel = self.bot.get_channel(target_id)
            if not channel:
                channel = await self.bot.fetch_channel(target_id)
                
            if not channel or not isinstance(channel, discord.VoiceChannel):
                return

            if self.radio.status == RadioStatusEnum.PLAYING and song:
                status_text = t('channel_status_playing', TITLE=song.title)
            else:
                status_text = None # Clear status when not playing or idle

            # Basic rate limit protection: only update if it actually changed
            # Note: channel.status availability depends on discord.py 2.4+
            current_status = getattr(channel, 'status', 'UNKNOWN_ATTR')
            if current_status == 'UNKNOWN_ATTR' or current_status != status_text:
                await channel.edit(status=status_text)
                
        except Exception as e:
            # We use debug here as missing permissions are common and shouldn't spam logs
            log.debug(f"Voice channel status update failed: {e}")

    async def _cleanup_stray_messages(self, channel, force=False):
        now = asyncio.get_event_loop().time()
        if not force and (now - self._last_cleanup < self.config.ui_cleanup_frequency): return 
        self._last_cleanup = now

        try:
            # IMPORTANT: Use the actual message IDs we are currently holding in memory
            # This is much safer than re-loading from the DB/file which might be stale
            current_station_id = self.radio.station_message.id if self.radio.station_message else None
            current_player_id = self.radio.now_playing_message.id if self.radio.now_playing_message else None
            
            # Search messages are ephemeral or tracked separately
            current_search_id = self.radio.embed_manager.load_message_id("search")
            
            known_ids = {current_station_id, current_player_id, current_search_id}
            # Remove None values from the set
            known_ids = {id for id in known_ids if id is not None}
            
            log.debug(f"[UI] Cleaning up. Known IDs: {known_ids}")
            
            to_delete = []
            async for msg in channel.history(limit=self.config.message_cleanup_limit):
                if msg.author.id == self.bot.user.id and msg.id not in known_ids:
                    to_delete.append(msg)
            
            if to_delete:
                if len(to_delete) > 1:
                    try:
                        # Attempt bulk delete (only works for messages < 14 days old)
                        await channel.delete_messages(to_delete)
                    except:
                        # Fallback to individual delete if bulk fails
                        for msg in to_delete:
                            await safe_delete_message(msg)
                else:
                    await safe_delete_message(to_delete[0])
        except Exception as ex:
            log.warning(f"UI Cleanup sweep failed: {ex}")

    async def _render_station_message(self, channel):
        if not self.radio.voice_channel_id:
            view = WelcomeLayout(self.radio)
        else:
            view = FrequencyStationView(self.radio)
            
        if not self.radio.station_message:
            msg_id = self.radio.embed_manager.load_message_id("station")
            if msg_id:
                self.radio.station_message = await safe_fetch_message(channel, msg_id)
            
        if self.radio.station_message:
            try: 
                await self.radio.station_message.edit(view=view)
            except: 
                self.radio.station_message = await channel.send(view=view)
        else:
            self.radio.station_message = await channel.send(view=view)
        
        self.radio.embed_manager.save_message_id("station", self.radio.station_message.id)

    async def _render_player_message(self, channel, song, show_player):
        
        if not show_player:
            # We want to ensure no player message exists
            msg_id = self.radio.embed_manager.load_message_id("player")
            if self.radio.now_playing_message:
                await safe_delete_message(self.radio.now_playing_message)
                self.radio.now_playing_message = None
            elif msg_id:
                # Active attempt to delete stale message from DB
                m = await safe_fetch_message(channel, msg_id)
                if m: await safe_delete_message(m)
            
            # Record that we have no player message anymore
            self.radio.embed_manager.save_message_id("player", None)
            return

        player_view = NowPlayingView(self.radio, song=song)
        
        if not self.radio.now_playing_message:
            msg_id = self.radio.embed_manager.load_message_id("player")
            if msg_id:
                self.radio.now_playing_message = await safe_fetch_message(channel, msg_id)
            
        if self.radio.now_playing_message:
            try:
                await self.radio.now_playing_message.edit(embed=None, view=player_view)
            except:
                self.radio.now_playing_message = await channel.send(view=player_view)
        else:
            self.radio.now_playing_message = await channel.send(view=player_view)
            
        self.radio.embed_manager.save_message_id("player", self.radio.now_playing_message.id)

    async def force_new_embed(self):
        """Immediately clears message IDs and triggers a fresh UI build."""
        async with self._ui_lock:
            # 1. Immediate state reset in memory
            self.radio.now_playing_message = None
            self.radio.station_message = None
            
            # 2. Reset IDs in DB so the next update sends NEW messages instead of editing
            self.radio.embed_manager.save_message_id("player", None)
            self.radio.embed_manager.save_message_id("station", None)
            self.radio.embed_manager.save_message_id("search", None)
            
            # 3. Trigger a full UI update (which will send new messages and then cleanup old ones)
            # We call the internal method directly to stay within the lock
            await self._update_ui_internal(self.radio.current_song)

    async def refresh_all_uis(self):
        """Triggers a lock-safe update of the current UI state."""
        await self.update_now_playing(self.radio.current_song)

    async def clear_voice_status(self, channel_id: int):
        """Public method to clear the status of a specific voice channel."""
        async with self._ui_lock:
            await self._update_channel_status(None, force_channel_id=channel_id)
