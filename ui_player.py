import asyncio
import discord
from discord.ui import Modal, TextInput, LayoutView, ActionRow, Container, Section, TextDisplay, Thumbnail, Separator
from ui_translate import t
from ui_icons import Icons
from ui_base import handle_ui_error, BaseView
from ui_utils import format_duration
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from core.models import Song
from ui_theme import Theme

_update_callback = None
_bot_ref = None
_config_ref = None

def init_player_ui(bot, config, update_fn):
    global _bot_ref, _config_ref, _update_callback
    _bot_ref = bot
    _config_ref = config
    _update_callback = update_fn

class StationSelect(discord.ui.Select):
    def __init__(self, radio, channels, custom_id="station_select"):
        self.radio = radio
        options = [
            discord.SelectOption(label=c.name, value=str(c.id), emoji=Icons.RADIO) for c in channels
        ]
        super().__init__(
            placeholder=t("placeholder_freq"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id=custom_id
        )

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        self.radio.dispatch(RadioAction.JOIN, channel_id, user=interaction.user)
        if not interaction.response.is_done():
            await interaction.response.defer()

class LanguageSelect(discord.ui.Select):
    def __init__(self, radio, custom_id="language_select"):
        self.radio = radio
        options = [
            discord.SelectOption(
                label=lang["label"], 
                value=lang["code"], 
                emoji=lang.get("emoji")
            ) for lang in radio.config.languages
        ]
        super().__init__(
            placeholder=t("placeholder_lang"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id=custom_id
        )

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        self.radio.language = selected
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        if _update_callback:
            await _update_callback(self.radio.current_song)

class DisconnectButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t('sever_uplink'),
            emoji=Icons.DISCONNECT,
            style=discord.ButtonStyle.secondary,
            custom_id="disconnect_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.DISCONNECT, user=interaction.user)
        if not interaction.response.is_done():
            await interaction.response.defer()

class PlayPauseButton(discord.ui.Button):
    def __init__(self, radio):
        is_paused = radio.status in [RadioStatusEnum.PAUSED, RadioStatusEnum.STOPPED, RadioStatusEnum.IDLE]
        label = None if radio.is_compact else (t('play_label') if is_paused else t('pause_label'))
        emoji = Icons.PLAY if is_paused else Icons.PAUSE
        
        is_idle_empty = (radio.status == RadioStatusEnum.IDLE) and (not radio.queue)
        
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id="play_pause_toggle",
            disabled=is_idle_empty
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.radio.status in [RadioStatusEnum.PAUSED, RadioStatusEnum.STOPPED, RadioStatusEnum.IDLE]:
            self.radio.dispatch(RadioAction.REPLAY, user=interaction.user)
        else:
            self.radio.dispatch(RadioAction.PAUSE, user=interaction.user)

class StopButton(discord.ui.Button):
    def __init__(self, radio):
        # Always secondary as requested (no red/green/blue here)
        # Disabled when IDLE or STOPPED
        is_disabled = radio.status in [RadioStatusEnum.IDLE, RadioStatusEnum.STOPPED]
        
        super().__init__(
            label=None if radio.is_compact else t('stop_label'),
            emoji=Icons.STOP,
            style=discord.ButtonStyle.secondary,
            custom_id="stop_button",
            disabled=is_disabled
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        self.radio.dispatch(RadioAction.STOP, user=interaction.user)

class ForwardButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('forward_label'),
            emoji=Icons.SKIP,
            style=discord.ButtonStyle.secondary,
            custom_id="forward_button",
            disabled=(not radio.queue)
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        self.radio.dispatch(RadioAction.SKIP, user=interaction.user)

class BackButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('back_label'),
            emoji=Icons.BACK,
            style=discord.ButtonStyle.secondary,
            custom_id="back_button",
            disabled=(not radio.history)
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        self.radio.dispatch(RadioAction.BACK, user=interaction.user)

class SeekButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('seek_label'),
            emoji=Icons.SEEK,
            style=discord.ButtonStyle.secondary,
            custom_id="seek_button",
            disabled=(radio.status in [RadioStatusEnum.STOPPED, RadioStatusEnum.IDLE])
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if self.radio.status in [RadioStatusEnum.IDLE, RadioStatusEnum.STOPPED]:
            await interaction.response.send_message(t("cannot_seek_stopped"), ephemeral=True)
            return
        modal = SeekModal(self.radio)
        await interaction.response.send_modal(modal)

class SeekModal(Modal):
    def __init__(self, radio):
        super().__init__(title=t("jump_modal_title"))
        self.radio = radio
        self.timestamp_input = TextInput(
            label=t("timestamp_input_label"),
            placeholder="01:30",
            style=discord.TextStyle.short,
            required=True,
            max_length=5
        )
        self.add_item(self.timestamp_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        ts = self.timestamp_input.value
        try:
            parts = ts.split(":")
            if len(parts) == 2:
                minutes, seconds = map(int, parts)
                total_seconds = minutes * 60 + seconds
            else:
                total_seconds = int(ts)
        except:
            await interaction.response.send_message(t("format_error"), ephemeral=True)
            return
        
        if not self.radio.current_song:
            await interaction.response.send_message(t("no_current_track"), ephemeral=True)
            return
            
        self.radio.dispatch(RadioAction.SEEK, total_seconds, user=interaction.user)
        if not interaction.response.is_done():
            await interaction.response.defer()

class VolumeButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('vol_label'),
            emoji=Icons.VOLUME,
            style=discord.ButtonStyle.secondary,
            custom_id="volume_button"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        modal = VolumeModal(self.radio)
        await interaction.response.send_modal(modal)

class VolumeModal(Modal):
    def __init__(self, radio):
        super().__init__(title=t("vol_modal_title"))
        self.radio = radio
        self.volume_input = TextInput(
            label=t("vol_input_label"),
            placeholder="50",
            style=discord.TextStyle.short,
            required=True,
            max_length=3
        )
        self.add_item(self.volume_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = int(self.volume_input.value)
            if 0 <= value <= 100:
                self.radio.dispatch(RadioAction.SET_VOLUME, value / 100, user=interaction.user)
                if not interaction.response.is_done():
                    await interaction.response.defer()
            else:
                await interaction.response.send_message(t("vol_range_error"), ephemeral=True)
        except:
            await interaction.response.send_message(t("invalid_number"), ephemeral=True)


class FavoriteToggleButton(discord.ui.Button):
    def __init__(self, radio, song: Song | None):
        # We start with HEART_PLUS / fav_add_label by default as a "Call to Action"
        # Since it's a shared view, we don't know which user's state to show until click.
        super().__init__(
            label=None if radio.is_compact else t('fav_add_label'),
            emoji=Icons.HEART_PLUS,
            style=discord.ButtonStyle.secondary,
            custom_id="player:favorite_toggle",
            disabled=(not song or song.is_resolving)
        )
        self.radio = radio
        self.song = song

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        if not self.song:
            return
            
        added = self.radio.fav_manager.toggle_favorite(interaction.user.id, self.song)
        
        # Update button state FOR THE NEXT ACTION
        # If just added, the button should now show "Remove"
        # If just removed, the button should now show "Favorite" (Add)
        self.emoji = Icons.HEART_MINUS if added else Icons.HEART_PLUS
        
        if not self.radio.is_compact:
            self.label = t('fav_remove_label') if added else t('fav_add_label')
        
        icon = Icons.HEART_PLUS if added else Icons.HEART_MINUS # Message icon
        msg = t("added_to_fav") if added else t("removed_from_fav")
        
        await interaction.response.send_message(f"{icon} {msg}", ephemeral=True)
        
        # Edit the message to reflect the new button state
        try:
            await interaction.message.edit(view=self.view)
        except Exception:
            pass


class UIStyleSelect(discord.ui.Select):
    def __init__(self, radio, custom_id="uistyle_select"):
        self.radio = radio
        options = [
            discord.SelectOption(label=t("full_mode_label"), value="full", description=t("full_mode_desc")),
            discord.SelectOption(label=t("compact_mode_label"), value="compact", description=t("compact_mode_desc"))
        ]
        super().__init__(
            placeholder=t("style_placeholder"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id=custom_id
        )

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        self.radio.is_compact = (selected == "compact")
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        if _update_callback:
            await _update_callback(self.radio.current_song)

class HelpButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t("help_label"),
            emoji=Icons.HELP,
            style=discord.ButtonStyle.secondary,
            custom_id="welcome:help"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        view = HelpView(self.radio)
        await interaction.response.send_message(embed=view.get_embed(), ephemeral=True)

class HelpView:
    def __init__(self, radio):
        self.radio = radio
        self.config = radio.config

    def get_embed(self) -> discord.Embed:
        prefix = self.config.command_prefix
        embed = discord.Embed(
            title=f"{Icons.HELP} {t('help_title')}",
            description=t("help_description"),
            color=Theme.PRIMARY
        )
        
        commands = [
            ("play [url/search]", t("help_play_desc")),
            ("pause", t("help_pause_desc")),
            ("stop", t("help_stop_desc")),
            ("skip", t("help_skip_desc")),
            ("back", t("help_back_desc")),
            ("volume [0-100]", t("help_vol_desc")),
            ("seek [time]", t("help_seek_desc")),
            ("queue", t("help_queue_desc")),
            ("join", t("help_join_desc")),
            ("disconnect", t("help_leave_desc"))
        ]
        
        for cmd, desc in commands:
            embed.add_field(name=f"`/{cmd}` vagy `{prefix}{cmd}`", value=desc, inline=False)
            
        return embed

class WelcomeLayout(BaseView):
    """
    Premium Welcome Screen for the Radio Bot.
    Shown when the bot is not connected to a voice channel.
    """
    def __init__(self, radio):
        super().__init__(radio)
        
        # Design Theme: Deep Blue / Cyberpunk accents
        embed_color = Theme.BACKGROUND
        
        # 1. Main Welcome Header
        header = Container(accent_color=embed_color)
        welcome_text = f"**{t('system_sync')}**\n{t('synchro_subtitle')}"
        header.add_item(TextDisplay(welcome_text))
        
        # 2. Controls Section
        guild = _bot_ref.get_guild(_config_ref.guild_id)
        if not guild:
            # Safer fallback: if get_guild fails, don't block. 
            # Dropdowns will be added on the next refresh/interaction once cache is ready.
            guild = None
                
        if guild:
            # Voice Channel Selection (Exclude AFK channel)
            afk_id = radio.config.afk_channel_id
            v_channels = [c for c in sorted(guild.voice_channels, key=lambda c: c.position) if c.id != afk_id][:25]
            row_station = ActionRow()
            row_station.add_item(StationSelect(radio, v_channels, custom_id="welcome:station_select"))
            header.add_item(row_station)
            
            # Language Selection
            row_lang = ActionRow()
            row_lang.add_item(LanguageSelect(radio, custom_id="welcome:language_select"))
            header.add_item(row_lang)
            
            # UI Style Selection
            row_style = ActionRow()
            row_style.add_item(UIStyleSelect(radio, custom_id="welcome:uistyle_select"))
            header.add_item(row_style)
            
            # Library Button
            from ui_search import LibraryButton, HistoryButton
            row_lib = ActionRow()
            row_lib.add_item(LibraryButton(radio, custom_id="welcome:library_button"))
            row_lib.add_item(HistoryButton(radio, custom_id="welcome:history_button"))
            row_lib.add_item(HelpButton(radio))
            header.add_item(row_lib)

        self.add_item(header)
        
        # 3. Mode Display (Always show, even in compact)
        status_box = Container(accent_color=Theme.SECONDARY)
        status_box.add_item(TextDisplay(f"**{t('standby_mode')}**\n*{t('standby_subtitle')}*"))
        self.add_item(status_box)

class FrequencyStationView(BaseView):
    """
    Standard Station View shown during active connection.
    """
    def __init__(self, radio):
        super().__init__(radio)
        
        main = Container(accent_color=Theme.BACKGROUND)
        main.add_item(TextDisplay(f"**{t('system_sync')}**\n{t('synchro_subtitle')}"))
        
        guild = _bot_ref.get_guild(_config_ref.guild_id)
        if guild:
            # Channel selection (Exclude AFK channel)
            afk_id = radio.config.afk_channel_id
            v_channels = [c for c in sorted(guild.voice_channels, key=lambda c: c.position) if c.id != afk_id][:25]
            row_select = ActionRow()
            row_select.add_item(StationSelect(radio, v_channels, custom_id="station:station_select"))
            main.add_item(row_select)
            
            # row 2: Language selection (MUST be separate row)
            row_lang = ActionRow()
            row_lang.add_item(LanguageSelect(radio, custom_id="station:language_select"))
            main.add_item(row_lang)
            
            # row 3: UI Style selection
            row_style = ActionRow()
            row_style.add_item(UIStyleSelect(radio, custom_id="station:uistyle_select"))
            main.add_item(row_style)
            
            # row 4: Management row
            mgmt_row = ActionRow()
            from ui_search import LibraryButton, HistoryButton
            mgmt_row.add_item(LibraryButton(radio, custom_id="station:library_button"))
            mgmt_row.add_item(HistoryButton(radio, custom_id="station:history_button"))
            mgmt_row.add_item(DisconnectButton(radio))
            main.add_item(mgmt_row)
            
        self.add_item(main)

class NowPlayingView(BaseView):
    def __init__(self, radio, song: Song | None = None):
        super().__init__(radio)
        song = song or radio.current_song
        
        # Color logic based on status
        if radio.status == RadioStatusEnum.PLAYING:
            accent_color = Theme.PLAYING
        elif radio.status == RadioStatusEnum.PAUSED:
            accent_color = Theme.PAUSED
        elif radio.status == RadioStatusEnum.STOPPED:
            accent_color = Theme.STOPPED
        else:
            accent_color = Theme.IDLE

        status_text = t("now_playing")
        if radio.status == RadioStatusEnum.PAUSED:
            status_text = t("paused")
        elif radio.status == RadioStatusEnum.STOPPED:
            status_text = t("stopped")
        elif radio.status == RadioStatusEnum.IDLE:
            status_text = t("idle")

        master = Container(accent_color=accent_color)
        
        def truncate(text, max_len):
            return (text[:max_len-3] + '...') if len(text) > max_len else text

        title = song.title if song else t("unknown")
        uploader = (song.uploader if song else None) or t("unknown")
        
        # Truncate for consistent UI width using config values
        truncated_title = truncate(title, radio.config.max_title_len)
        truncated_uploader = truncate(uploader, radio.config.max_uploader_len)

        source = song.source if song else None
        if not source and song and song.webpage_url:
            if "youtube.com" in song.webpage_url or "youtu.be" in song.webpage_url:
                source = "YouTube"
            elif "soundcloud.com" in song.webpage_url:
                source = "SoundCloud"
        
        # Rich info for both modes (only buttons change)
        current_status_icon = Icons.STATUS
        if radio.status == RadioStatusEnum.PLAYING:
            current_status_icon = Icons.HEADPHONES
        elif radio.status == RadioStatusEnum.PAUSED:
            current_status_icon = Icons.PAUSE
        elif radio.status == RadioStatusEnum.STOPPED:
            current_status_icon = Icons.STOP
        elif radio.status == RadioStatusEnum.IDLE:
            current_status_icon = Icons.IDLE

        title_display = truncated_title
        web_url = song.webpage_url if song else None
        if web_url:
            title_display = f"[{truncated_title}]({web_url})"

        info_lines = [
            f"**{current_status_icon} {status_text}**",
            f"**{t('uploader')}:** {truncated_uploader}",
            f"**{t('title')}:** {title_display}"
        ]
        if source:
            info_lines.append(f"**{t('source')}:** {source}")
        
        elapsed = int(radio.track_start_offset)
        if radio.track_start_time and radio.status == RadioStatusEnum.PLAYING:
            elapsed += int(asyncio.get_event_loop().time() - radio.track_start_time)
        duration = song.duration if song else 0
        bar_width = radio.config.progress_bar_width
        def create_progress_bar(current, total, width=None):
            width = width or bar_width
            if total <= 0:
                return f"{Icons.PB_START}{str(Icons.PB_EMPTY) * (width-2)}{Icons.PB_RIGHT}"
            
            progress = min(1.0, max(0.0, current / total))
            filled_count = int(progress * (width - 1))
            
            parts = []
            for i in range(width):
                if i == 0:
                    parts.append(Icons.PB_START if filled_count == 0 else Icons.PB_LEFT)
                elif i == width - 1:
                    parts.append(Icons.PB_END if progress >= 1.0 else Icons.PB_RIGHT)
                elif i == filled_count:
                    parts.append(Icons.PB_KNOB)
                elif i < filled_count:
                    parts.append(Icons.PB_FULL)
                else:
                    parts.append(Icons.PB_EMPTY)
            
            return "".join(map(str, parts))

        time_readout = f"`{format_duration(elapsed)} / {format_duration(duration) if duration else t('unknown')}`"
        progress_bar = create_progress_bar(elapsed, duration)
        info_lines.extend([
            f"\n{time_readout}\n",
            f"{progress_bar}"
        ])
        
        if radio.last_user:
            channel_name = ""
            if radio.voice and radio.voice.channel:
                channel_name = f" @ {radio.voice.channel.mention}"
            elif radio.voice_channel_id:
                # Fallback if voice client is connecting
                channel_name = " @ ..."
                
            info_lines.append(f"\n{t('tuned_by')} {radio.last_user.mention}{channel_name}")

        thumb = None
        thumb_url = song.thumbnail_url if song else None
        # If idle and no song thumbnail, use bot avatar
        if not thumb_url and radio.status == RadioStatusEnum.IDLE and _bot_ref:
            thumb_url = str(_bot_ref.user.display_avatar.url)
        
        if thumb_url:
            thumb = Thumbnail(thumb_url)

        if thumb:
            master.add_item(Section("\n".join(info_lines), accessory=thumb))
        else:
            master.add_item(TextDisplay("\n".join(info_lines)))
        
        # Add a separator and move buttons inside the container
        master.add_item(Separator())
        
        from ui_search import WebLinkButton, QueueViewButton, SearchButton
        
        row1 = ActionRow()
        row1.add_item(BackButton(radio))
        row1.add_item(PlayPauseButton(radio))
        row1.add_item(StopButton(radio))
        row1.add_item(ForwardButton(radio))
        row1.add_item(FavoriteToggleButton(radio, song))
        master.add_item(row1)
        
        row2 = ActionRow()
        row2.add_item(SeekButton(radio))
        row2.add_item(VolumeButton(radio))
        row2.add_item(SearchButton(radio))
        row2.add_item(WebLinkButton(radio, custom_id="player:weblink_button"))
        row2.add_item(QueueViewButton(radio))
        master.add_item(row2)
        
        # row3 containing LibraryButton removed as requested
        
        # Finally, add the master (now containing everything) to the view
        self.add_item(master)
