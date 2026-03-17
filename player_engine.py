import asyncio
import discord
from typing import Optional, Callable, Dict, Any
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from core.models import Song
from core.radio import RadioManager
from logger import log

class RadioPlayer:
    def __init__(self, bot: discord.Client, config, radio: RadioManager, 
                 update_ui_callback: Callable, refresh_ui_callback: Callable, 
                 cleanup_ui_callback: Optional[Callable] = None):
        self.bot = bot
        self.config = config
        self.radio = radio
        self.update_ui = update_ui_callback
        self.refresh_ui = refresh_ui_callback
        self.cleanup_ui = cleanup_ui_callback
        # Idle/Timeout constants
        self.TIMEOUT = self.config.afk_timeout_seconds
        self.solitary_start = None
        self.idle_start = None
        
        # Link the manager back to a refresh callback
        self.radio.on_state_change = self.update_ui

    async def ensure_voice(self) -> Optional[discord.VoiceClient]:
        """Ensures the bot is connected to the correct voice channel."""
        guild = self.bot.get_guild(self.config.guild_id)
        if not guild or not self.radio.voice_channel_id:
            return None
            
        channel = guild.get_channel(self.radio.voice_channel_id)
        if not channel:
            return None

        if guild.voice_client:
            self.radio.voice = guild.voice_client
            if self.radio.voice.channel.id != channel.id:
                await self.radio.voice.move_to(channel)
        else:
            self.radio.voice = await channel.connect(reconnect=True)
        return self.radio.voice

    async def run_loop(self):
        """Main player lifecycle loop."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                voice = await self.ensure_voice()
                
                # 1. State: DISCONNECTED
                if not voice:
                    await self._handle_disconnected_state()
                    continue

                # 2. Monitor Solitary Status
                if await self._check_solitary_timeout(voice):
                    continue

                # 3. State: IDLE, STOPPED, or PAUSED (if not currently in a playback monitor loop)
                if self.radio.status in [RadioStatusEnum.IDLE, RadioStatusEnum.STOPPED, RadioStatusEnum.PAUSED]:
                    if await self._handle_idle_state(voice):
                        continue
                else:
                    self.idle_start = None

                # 4. State: PLAYING (Song Selection & Start)
                if self.radio.status == RadioStatusEnum.PLAYING:
                    await self._start_playback(voice)
                
                # 5. Safety sleep to prevent busy-waiting
                await asyncio.sleep(0.5)

            except Exception as e:
                import traceback
                log.error(f"Player crash: {e}")
                log.error(traceback.format_exc())
                await asyncio.sleep(self.config.error_retry_seconds)

    async def _handle_disconnected_state(self):
        """Logic when voice is not connected."""
        try:
            action, data = await asyncio.wait_for(self.radio.action_queue.get(), timeout=5.0)
            if action == RadioAction.JOIN:
                self.radio.voice_channel_id = data
                self.radio.status = RadioStatusEnum.PLAYING
            elif action == RadioAction.ADD_EXT_LINK:
                await self.radio.add_external_link(data)
                self.radio.status = RadioStatusEnum.PLAYING
                await self.refresh_ui()
            elif action == RadioAction.DISCONNECT:
                await self._disconnect(None)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            log.error(f"[PLAYER] Error in disconnected state handler: {e}")

    async def _check_solitary_timeout(self, voice) -> bool:
        """Returns True if the bot disconnected due to being alone."""
        real_members = [m for m in voice.channel.members if not m.bot]
        if len(real_members) == 0:
            if self.solitary_start is None:
                log.info(f"[SOLITARY] Bot is alone. Starting {self.TIMEOUT}s countdown.")
                self.solitary_start = asyncio.get_event_loop().time()
            elif asyncio.get_event_loop().time() - self.solitary_start >= self.TIMEOUT:
                log.info(f"Auto-disconnecting: Bot was alone for {self.TIMEOUT}s.")
                self.radio.dispatch(RadioAction.DISCONNECT)
                self.solitary_start = None
                await asyncio.sleep(1)
                return True
        else:
            if self.solitary_start is not None:
                log.info("[SOLITARY] Member joined or present. Resetting countdown.")
            self.solitary_start = None
        return False

    async def _handle_idle_state(self, voice) -> bool:
        """Logic when voice is connected but nothing is playing."""
        if self.idle_start is None:
            self.idle_start = asyncio.get_event_loop().time()
        elif asyncio.get_event_loop().time() - self.idle_start >= self.TIMEOUT:
            log.info("Auto-disconnecting: Dynamic idle timeout (5 mins).")
            self.radio.dispatch(RadioAction.DISCONNECT)
            self.idle_start = None
            return True

        try:
            action, data = await asyncio.wait_for(self.radio.action_queue.get(), timeout=5.0)
            self.idle_start = None 
            
            if action == RadioAction.SET_VOLUME:
                self.radio.volume = data
                return True
            elif action == RadioAction.JOIN:
                self.radio.voice_channel_id = data
            elif action == RadioAction.DISCONNECT:
                await self._disconnect(voice)
                return True
            elif action == RadioAction.ADD_EXT_LINK:
                await self.radio.add_external_link(data)
                await self.refresh_ui()
            elif action == RadioAction.REPLAY:
                # IMPORTANT: If we are STOPPED but have a current_song, we want to play it, not skip to next.
                if self.radio.status == RadioStatusEnum.STOPPED and self.radio.current_song:
                    self.radio.is_seeking = True
                    self.radio.seek_position = 0
                elif self.radio.status == RadioStatusEnum.PAUSED and self.radio.current_song:
                    self.radio.is_seeking = True
                    self.radio.seek_position = self.radio.track_start_offset
            elif action == RadioAction.SEEK:
                log.info(f"[PLAYER] Idle Seeking to: {data}s")
                self.radio.seek_position = data
                self.radio.track_start_offset = data
                self.radio.is_seeking = True
                await self.update_ui(self.radio.current_song)
                return True
            else: 
                return True
            
            self.radio.status = RadioStatusEnum.PLAYING
            return False
        except asyncio.TimeoutError:
            return True

    async def _disconnect(self, voice):
        self.radio.voice_channel_id = None
        self.radio.status = RadioStatusEnum.IDLE
        self.radio.current_song = None
        if voice: await voice.disconnect()
        if self.cleanup_ui: await self.cleanup_ui()
        self.idle_start = None

    async def _start_playback(self, voice):
        """Prepares and starts audio playback."""
        # 1. Skip if seeking/no song
        if not self.radio.current_song or not self.radio.is_seeking:
            if self.radio.current_song and not self.radio.is_seeking:
                self.radio.history_manager.add(self.radio.current_song)
                
            if self.radio.queue:
                self.radio.current_song = self.radio.queue.pop(0)
                self.radio.is_seeking = False
            else:
                self.radio.status = RadioStatusEnum.IDLE
                self.radio.current_song = None
                self.radio.is_seeking = False
                await self.update_ui(None)
                return
        
        song = self.radio.current_song
        self.radio.is_seeking = False
        source_path = await self._resolve_source(song)
        if not source_path:
            self.radio.current_song = None
            return

        # 2. Create FFmpeg Source
        audio_source = self._create_ffmpeg_source(source_path)
        
        # 3. Play and Monitor
        self.radio.track_start_time = asyncio.get_event_loop().time()
        self.radio.track_start_offset = self.radio.seek_position or 0.0
        self.radio.seek_position = None
        
        done = asyncio.Event()
        def after_playing(error):
            if error:
                # Suppress "read of closed file" error which is common noise when stopping/skipping FFmpeg
                err_msg = str(error)
                if "read of closed file" not in err_msg.lower():
                    log.error(f"[PLAYER] Playback error: {error}")
                else:
                    log.debug(f"[PLAYER] Suppressed noise: {err_msg}")
            self.bot.loop.call_soon_threadsafe(done.set)

        while voice.is_playing() or voice.is_paused():
            await asyncio.sleep(0.1)
        
        voice.play(audio_source, after=after_playing)
        log.info(f"[PLAYER] Started playing: {song.uploader} - {song.title} ({song.duration}s)")
        await self.update_ui(song)

        # 4. Interactive loop during playback
        await self._playback_monitor_loop(voice, song, done)
        
        # 5. Safety: Wait for the voice player thread to fully exit before cleaning up
        # This prevents the "read of closed file" error during SKIP/STOP/SEEK
        await done.wait()

        # 6. Cleanup track state
        if not done.is_set(): # This part is now technically redundant due to await above but kept for logic
            log.info(f"[PLAYER] Monitor loop broke before track finished: {song.title}")
        else:
            log.info(f"[PLAYER] Track finished normally: {song.title}")

        self.radio.track_start_time = None
        self.radio.track_start_offset = 0.0
        audio_source.cleanup()

    async def _resolve_source(self, song: Song) -> Optional[str]:
        source_path = song.path
        if song.is_external:
            if not song.stream_url or song.is_resolving:
                await self.update_ui(song)
                from providers import resolve_any
                resolved = await resolve_any(source_path, self.radio.providers)
                if resolved: song.update(resolved)
            
            if song.stream_url:
                return song.stream_url
            return None
        return source_path

    def _create_ffmpeg_source(self, source_path: str):
        # Even more robust reconnect options for YouTube/SoundCloud
        reconnect_opts = (
            "-reconnect 1 "
            "-reconnect_at_eof 1 "
            "-reconnect_streamed 1 "
            "-reconnect_delay_max 5 "
            "-reconnect_on_network_error 1 "
            "-reconnect_on_http_error 4xx,5xx"
        )
        # Add User-Agent and probe settings to FFmpeg as well
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        before_opts = f"-nostdin {reconnect_opts} -user_agent \"{user_agent}\" -analyzeduration 20M -probesize 20M"
        if self.radio.seek_position is not None:
            before_opts += f" -ss {self.radio.seek_position}"
        
        filter_chain = f"volume={self.radio.volume}"
        return discord.FFmpegOpusAudio(
            source_path,
            executable=self.config.ffmpeg_path,
            before_options=before_opts,
            options=f'-vn -filter:a "{filter_chain}"'
        )

    async def _playback_monitor_loop(self, voice, song, done):
        """Listens for actions while a track is playing."""
        while not done.is_set():
            try:
                # Continuous solitary check
                if await self._check_solitary_timeout(voice):
                    break

                action_task = asyncio.create_task(self.radio.action_queue.get())
                done_task = asyncio.create_task(done.wait())
                
                finished, pending = await asyncio.wait(
                    [action_task, done_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=5.0
                )
                for task in pending: task.cancel()

                if action_task in finished:
                    action, data = action_task.result()
                    if await self._handle_playback_action(voice, action, data, song):
                        break # break monitor loop to re-evaluate state
                
                if done_task in finished:
                    break
            except asyncio.TimeoutError:
                continue

    async def _handle_playback_action(self, voice, action, data, song) -> bool:
        """Processes an action and returns True if playback should break."""
        if action == RadioAction.SKIP:
            log.info("[PLAYER] Skipping current track.")
            self.radio.is_seeking = False
            voice.stop()
            return True
        elif action == RadioAction.SEEK:
            log.info(f"[PLAYER] Seeking to: {data}s")
            self.radio.seek_position = data
            self.radio.is_seeking = True
            
            # If we are paused, update the offset too so the UI looks correct immediately
            if self.radio.status == RadioStatusEnum.PAUSED:
                self.radio.track_start_offset = data
                
            voice.stop()
            
            # If paused, we need to manually trigger a UI update because the monitor loop breaks
            if self.radio.status == RadioStatusEnum.PAUSED:
                await self.update_ui(song)
            return True
        elif action == RadioAction.SET_VOLUME:
            log.info(f"[PLAYER] Volume changed to: {int(data*100)}%")
            self.radio.volume = data
            if self.radio.track_start_time:
                elapsed = (asyncio.get_event_loop().time() - self.radio.track_start_time)
                self.radio.seek_position = self.radio.track_start_offset + elapsed
            else:
                self.radio.seek_position = self.radio.track_start_offset
            self.radio.is_seeking = True
            voice.stop()
            return True
        elif action == RadioAction.PAUSE:
            if voice.is_playing():
                log.info("[PLAYER] Pausing playback.")
                voice.pause()
                if self.radio.track_start_time:
                    self.radio.track_start_offset += (asyncio.get_event_loop().time() - self.radio.track_start_time)
                self.radio.track_start_time = None
                self.radio.status = RadioStatusEnum.PAUSED
                await self.update_ui(song)
            return False
        elif action == RadioAction.REPLAY:
            if self.radio.status == RadioStatusEnum.PAUSED:
                log.info("[PLAYER] Resuming playback.")
                voice.resume()
                self.radio.track_start_time = asyncio.get_event_loop().time()
                self.radio.status = RadioStatusEnum.PLAYING
                await self.update_ui(song)
                return False
            else:
                log.info("[PLAYER] Replaying track from start.")
                self.radio.seek_position = 0
                self.radio.is_seeking = True
                voice.stop()
                return True
        elif action == RadioAction.BACK:
            log.info("[PLAYER] Moving back to previous track.")
            if self.radio.history:
                if self.radio.current_song:
                    self.radio.queue.insert(0, self.radio.current_song)
                self.radio.current_song = self.radio.history.pop(0)
                self.radio.seek_position = None
                self.radio.is_seeking = True
                voice.stop()
                return True
            else:
                self.radio.seek_position = 0
                self.radio.is_seeking = True
                voice.stop()
                return True
        elif action == RadioAction.STOP:
            log.info("[PLAYER] Stopping playback.")
            self.radio.status = RadioStatusEnum.STOPPED
            self.radio.track_start_offset = 0.0
            self.radio.track_start_time = None
            voice.stop()
            await self.update_ui(song)
            return True
        elif action == RadioAction.DISCONNECT:
            await self._disconnect(voice)
            return True
        elif action == RadioAction.ADD_EXT_LINK:
            await self.radio.add_external_link(data)
            await self.refresh_ui()
            return False
        return False
