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
        self.solitary_timeout = self.config.solitary_timeout_seconds
        self.solitary_start = None
        self._voice_lock = asyncio.Lock()
        
        # Link the manager back to a refresh callback
        self.radio.on_state_change = self.update_ui

    async def ensure_voice(self) -> Optional[discord.VoiceClient]:
        """Ensures the bot is connected to the correct voice channel."""
        async with self._voice_lock:
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild or not self.radio.voice_channel_id:
                return None
                
            channel = guild.get_channel(self.radio.voice_channel_id)
            if not channel:
                log.warning(f"[VOICE] Target channel {self.radio.voice_channel_id} not found in guild {guild.name}")
                return None

            if guild.voice_client:
                if guild.voice_client.is_connected():
                    self.radio.voice = guild.voice_client
                    if self.radio.voice.channel.id != channel.id:
                        log.info(f"[VOICE] Moving from {self.radio.voice.channel.name} to {channel.name}")
                        await self.radio.voice.move_to(channel)
                    return self.radio.voice
                else:
                    log.warning(f"[VOICE] Dead voice client found for guild {guild.name}. Cleaning up.")
                    try:
                        await guild.voice_client.disconnect(force=True)
                    except:
                        pass
                    self.radio.voice = None

            # Check if someone else is already there before connecting
            found_bot = None
            for member in channel.members:
                if member.bot and member.id != self.bot.user.id:
                    found_bot = member
                    break
            
            if found_bot:
                log.info(f"[VOICE] Note: Another bot ({found_bot.name}) is in {channel.name}. Joining anyway.")
            
            # Check for specifically forbidden bots
            for member in channel.members:
                if member.bot and member.id in self.config.forbidden_bot_ids:
                    log.warning(f"[VOICE] Forbidden bot {member.name} ({member.id}) detected in {channel.name}. Aborting join.")
                    return None
            
            try:
                log.info(f"[VOICE] Connecting to {channel.name} in guild {guild.name}...")
                # Increase timeout to 30s as Discord Gateway can be slow on some networks (e.g. Windows)
                self.radio.voice = await channel.connect(reconnect=True, timeout=30.0, self_deaf=True)
                log.info(f"[VOICE] Successfully connected to {channel.name}")
            except (asyncio.TimeoutError, discord.errors.ClientException, Exception) as e:
                log.warning(f"[VOICE] Connection attempt failed: {type(e).__name__}: {e}")
                self.radio.voice = None
                return None

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

                # 4. State: PLAYING (Song Selection & Start)
                if self.radio.status == RadioStatusEnum.PLAYING:
                    await self._start_playback(voice)
                
                # 5. Safety sleep to prevent busy-waiting
                await asyncio.sleep(self.config.player_loop_sleep)

            except Exception as e:
                import traceback
                log.error(f"Player crash: {e}")
                log.error(traceback.format_exc())
                await asyncio.sleep(self.config.error_retry_seconds)

    async def _handle_disconnected_state(self):
        """Logic when voice is not connected."""
        self.solitary_start = None
        try:
            action, data = await asyncio.wait_for(self.radio.action_queue.get(), timeout=self.config.action_timeout)
            if action == RadioAction.JOIN:
                self.radio.voice_channel_id = data
                self.radio.status = RadioStatusEnum.PLAYING
            elif action == RadioAction.ADD_EXT_LINK:
                await self.radio.add_external_link(data, user=self.radio.last_user)
                self.radio.status = RadioStatusEnum.PLAYING
                await self.refresh_ui()
            elif action == RadioAction.ADD_SONGS:
                await self.radio.add_songs(data, user=self.radio.last_user)
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
                log.info(f"[SOLITARY] Bot is alone. Starting {self.solitary_timeout}s countdown.")
                self.solitary_start = asyncio.get_event_loop().time()
            elif asyncio.get_event_loop().time() - self.solitary_start >= self.solitary_timeout:
                log.info(f"Auto-disconnecting: Bot was alone for {self.solitary_timeout}s.")
                self.solitary_start = None
                await self._disconnect(voice)
                return True
        else:
            if self.solitary_start is not None:
                log.info("[SOLITARY] Member joined or present. Resetting countdown.")
            self.solitary_start = None
        return False

    async def _handle_idle_state(self, voice) -> bool:
        """Logic when voice is connected but nothing is playing."""
        try:
            action, data = await asyncio.wait_for(self.radio.action_queue.get(), timeout=self.config.action_timeout)
            self.solitary_start = None # Reset solitary timer on interaction
            
            if action == RadioAction.SET_VOLUME:
                self.radio.volume = data
                return True
            elif action == RadioAction.JOIN:
                self.radio.voice_channel_id = data
            elif action == RadioAction.DISCONNECT:
                await self._disconnect(voice)
                return True
            elif action == RadioAction.ADD_EXT_LINK:
                await self.radio.add_external_link(data, user=self.radio.last_user)
                await self.refresh_ui()
            elif action == RadioAction.ADD_SONGS:
                await self.radio.add_songs(data, user=self.radio.last_user)
                await self.refresh_ui()
            elif action == RadioAction.REPLAY:
                # IMPORTANT: If we are STOPPED but have a current_song, we want to play it, not skip to next.
                if self.radio.status == RadioStatusEnum.STOPPED and self.radio.current_song:
                    self.radio.is_seeking = True
                    self.radio.seek_position = 0
                elif self.radio.status == RadioStatusEnum.PAUSED and self.radio.current_song:
                    self.radio.is_seeking = True
                    self.radio.seek_position = None # Just resume
            elif action == RadioAction.SKIP:
                if self.radio.future_queue or self.radio.queue:
                    self.radio.status = RadioStatusEnum.PLAYING
                    return False
                return True
            elif action == RadioAction.BACK:
                back_song = self.radio.history_manager.pop_latest()
                if back_song:
                    if self.radio.current_song:
                        self.radio.future_queue.insert(0, self.radio.current_song)
                    self.radio.current_song = back_song
                    self.radio.is_navigating = True
                    self.radio.is_seeking = True # Prevent _start_playback from popping
                    self.radio.status = RadioStatusEnum.PLAYING
                    return False
                return True
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
        self.solitary_start = None

    async def _start_playback(self, voice):
        """Prepares and starts audio playback."""
        # 1. Selection logic
        if not self.radio.current_song or not self.radio.is_seeking:
            if self.radio.future_queue:
                # Coming back from history browsing
                self.radio.current_song = self.radio.future_queue.pop(0)
                self.radio.is_navigating = True
            elif self.radio.queue:
                self.radio.current_song = self.radio.queue.pop(0)
                self.radio.is_navigating = False
            else:
                self.radio.status = RadioStatusEnum.IDLE
                self.radio.current_song = None
                self.radio.is_navigating = False
                await self.update_ui(None)
                return
        
        song = self.radio.current_song
        self.radio.is_seeking = False
        source_path = await self._resolve_source(song)
        if not source_path:
            self.radio.current_song = None
            return

        # 2. History Recording (Only if not browsing)
        # Move AFTER _resolve_source to ensure we have the real title
        if not self.radio.is_navigating:
            self.radio.history_manager.add(self.radio.current_song)

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
                if resolved:
                    song.update(resolved)
                    # Update cache with real metadata
                    self.radio.db.set_cache(
                        url=source_path,
                        title=song.title,
                        uploader=song.uploader or "Unknown",
                        duration=song.duration,
                        thumbnail_url=song.thumbnail_url or ""
                    )
            
            if song.stream_url:
                return song.stream_url
            return None
        return source_path

    def _create_ffmpeg_source(self, source_path: str):
        # Configurable reconnect options for YouTube/SoundCloud
        reconnect_opts = self.config.ffmpeg_reconnect_options
        # Add User-Agent and probe settings to FFmpeg as well
        user_agent = self.config.user_agent
        
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
                    timeout=self.config.action_timeout
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
        self.solitary_start = None # Reset solitary timer on interaction
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
            log.info("[PLAYER] Navigating back in history.")
            
            # 1. Undoplay current: remove it from history since it was added at start of playback
            if not self.radio.is_navigating and self.radio.current_song:
                self.radio.history_manager.pop_latest()
                
            # 2. Get the real previous song
            back_song = self.radio.history_manager.pop_latest()
            if back_song:
                if self.radio.current_song:
                    self.radio.future_queue.insert(0, self.radio.current_song)
                self.radio.current_song = back_song
                self.radio.is_navigating = True
                self.radio.is_seeking = True
                voice.stop()
                return True
            
            # If no history, just restart current
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
            await self.radio.add_external_link(data, user=self.radio.last_user)
            await self.refresh_ui()
            return False
        elif action == RadioAction.ADD_SONGS:
            await self.radio.add_songs(data, user=self.radio.last_user)
            await self.refresh_ui()
            return False
        return False
