import asyncio
import discord
from ui_translate import t, init_translate
from radio_actions import RadioState as RadioStatusEnum
from core.models import Song
from ui_player import WelcomeLayout, FrequencyStationView, NowPlayingView, init_player_ui
from ui_search import FullQueueView
from ui_utils import safe_delete_message, safe_fetch_message, get_dominant_color
from logger import log

class UIManager:
    def __init__(self, bot: discord.Client, config, radio):
        self.bot = bot
        self.config = config
        self.radio = radio
        self._ui_lock = asyncio.Lock()
        
        # Initialize sub-systems
        init_translate(radio)
        init_player_ui(bot, config, self.update_now_playing)

    async def update_now_playing(self, song: Song | None):
        """Public entry point for UI updates with locking."""
        async with self._ui_lock:
            await self._update_ui_internal(song)

    async def _update_ui_internal(self, song: Song | None):
        """Internal UI rendering logic."""
        try:
            # Handle potential dict fallback from older code
            if isinstance(song, dict):
                song = None
                
            has_no_song = song is None or not song.path
            
            if not self.bot or self.bot.is_closed(): return
            
            # 1. Presence Update
            await self._update_presence(song)

            channel = self.bot.get_channel(self.config.radio_text_channel_id)
            if not channel:
                try: channel = await self.bot.fetch_channel(self.config.radio_text_channel_id)
                except: return

            # 2. Aggressive Cleanup
            await self._cleanup_stray_messages(channel)

            # 3. Handle Station Message (Header)
            await self._render_station_message(channel)

            # 4. Handle Player Message (Centerpiece)
            await self._render_player_message(channel, song, has_no_song)

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

    async def _cleanup_stray_messages(self, channel):
        try:
            current_station_id = self.radio.embed_manager.load_message_id("station")
            current_player_id = self.radio.embed_manager.load_message_id("player")
            current_search_id = self.radio.embed_manager.load_message_id("search")
            known_ids = {current_station_id, current_player_id, current_search_id}
            
            async for msg in channel.history(limit=50):
                if msg.author.id == self.bot.user.id and msg.id not in known_ids:
                    await safe_delete_message(msg)
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

    async def _render_player_message(self, channel, song, has_no_song):
        show_player = not has_no_song or self.radio.voice_channel_id
        
        if not show_player:
            if self.radio.now_playing_message:
                await safe_delete_message(self.radio.now_playing_message)
                self.radio.now_playing_message = None
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
        """Deletes all messages and re-posts them for a fresh start."""
        async with self._ui_lock:
            channel = self.bot.get_channel(self.config.radio_text_channel_id)
            if not channel: return
            
            self.radio.embed_manager.save_message_id("player", None)
            self.radio.embed_manager.save_message_id("station", None)
            self.radio.embed_manager.save_message_id("search", None)
            
            async for msg in channel.history(limit=50):
                if msg.author.id == self.bot.user.id:
                    await safe_delete_message(msg)
            
            self.radio.now_playing_message = None
            self.radio.station_message = None
            await self._update_ui_internal(self.radio.current_song)

    async def refresh_all_uis(self):
        """Triggers a lock-safe update of the current UI state."""
        await self.update_now_playing(self.radio.current_song)
