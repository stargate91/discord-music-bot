import discord
from discord import app_commands
from typing import Optional
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from ui_translate import t
from ui_utils import respond

def setup_commands(tree: app_commands.CommandTree, radio):
    async def restricted_channel_check(interaction: discord.Interaction) -> bool:
        # Check if limited to a specific channel
        if interaction.channel_id != radio.config.radio_text_channel_id:
            return False
        return True

    tree.interaction_check = restricted_channel_check

    @tree.command(name="play", description=t("help_play_desc"))
    @app_commands.describe(url=t("search_placeholder"))
    async def play(interaction: discord.Interaction, url: Optional[str] = None):
        if not interaction.user.voice:
            await respond(interaction, t("no_permission"), delete_after=radio.config.notification_timeout)
            return

        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return

        if not url:
            if radio.status == RadioStatusEnum.PAUSED:
                radio.dispatch(RadioAction.REPLAY, user=interaction.user)
                await respond(interaction, t("resuming_feedback"), delete_after=radio.config.notification_timeout)
            else:
                await respond(interaction, t("nothing_playing"), delete_after=radio.config.notification_timeout)
            return
            
        await interaction.response.defer(ephemeral=True)
        url_strip = url.strip()
        
        if radio.voice_channel_id is None:
            radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
            
        radio.dispatch(RadioAction.ADD_EXT_LINK, url_strip, user=interaction.user)
        await respond(interaction, t("weblink_added"), delete_after=radio.config.notification_timeout)

    @tree.command(name="pause", description=t("help_pause_desc"))
    async def pause(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return

        if radio.status == RadioStatusEnum.PLAYING:
            radio.dispatch(RadioAction.PAUSE, user=interaction.user)
            await respond(interaction, t("pausing"), delete_after=radio.config.notification_timeout)
        else:
            await respond(interaction, t("cannot_pause_stopped"), delete_after=radio.config.notification_timeout)

    @tree.command(name="stop", description=t("help_stop_desc"))
    async def stop(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        radio.dispatch(RadioAction.STOP, user=interaction.user)
        await respond(interaction, t("stopping"), delete_after=radio.config.notification_timeout)

    @tree.command(name="disconnect", description=t("help_leave_desc"))
    async def disconnect(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        radio.dispatch(RadioAction.DISCONNECT, user=interaction.user)
        await respond(interaction, t("severing"), delete_after=radio.config.notification_timeout)

    @tree.command(name="skip", description=t("help_skip_desc"))
    async def skip(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        if not radio.queue:
            await respond(interaction, t("no_next_track"), delete_after=radio.config.notification_timeout)
            return
        radio.dispatch(RadioAction.SKIP, user=interaction.user)
        await respond(interaction, t("forwarding"), delete_after=radio.config.notification_timeout)

    @tree.command(name="back", description=t("help_back_desc"))
    async def back(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        if not radio.history:
            await respond(interaction, t("no_prev_track"), delete_after=radio.config.notification_timeout)
            return
        radio.dispatch(RadioAction.BACK, user=interaction.user)
        await respond(interaction, t("back_label") + "...", delete_after=radio.config.notification_timeout)

    @tree.command(name="join", description=t("help_join_desc"))
    async def join(interaction: discord.Interaction):
        if not interaction.user.voice:
            await respond(interaction, t("no_permission"), delete_after=radio.config.notification_timeout)
            return
        
        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return

        radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
        await respond(interaction, f"{t('syncing')} ({interaction.user.voice.channel.name})", delete_after=radio.config.notification_timeout)

    @tree.command(name="volume", description=t("help_vol_desc"))
    @app_commands.describe(percent=t("help_vol_desc"))
    async def volume(interaction: discord.Interaction, percent: int):
        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
            
        if 0 <= percent <= 100:
            radio.dispatch(RadioAction.SET_VOLUME, percent / 100, user=interaction.user)
            await respond(interaction, f"{t('vol_set')} {percent}%", delete_after=radio.config.notification_timeout)
        else:
            await respond(interaction, t("vol_range_error"), delete_after=radio.config.notification_timeout)

    @tree.command(name="seek", description=t("help_seek_desc"))
    @app_commands.describe(time=t("help_seek_desc"))
    async def seek(interaction: discord.Interaction, time: str):
        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return

        if radio.status in [RadioStatusEnum.IDLE, RadioStatusEnum.STOPPED]:
            await respond(interaction, t("cannot_seek_stopped"), delete_after=radio.config.notification_timeout)
            return
            
        if not radio.current_song:
            await respond(interaction, t("no_current_track"), delete_after=radio.config.notification_timeout)
            return
            
        try:
            parts = time.split(":")
            if len(parts) == 2:
                minutes, seconds = map(int, parts)
                total_seconds = minutes * 60 + seconds
            else:
                total_seconds = int(time)
        except:
            await respond(interaction, t("format_error"), delete_after=radio.config.notification_timeout)
            return

        radio.dispatch(RadioAction.SEEK, total_seconds, user=interaction.user)
        await respond(interaction, f"{t('jumping')} {time}", delete_after=radio.config.notification_timeout)

    @tree.command(name="queue", description=t("help_queue_desc"))
    async def queue(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, t("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        from ui_search import FullQueueView
        view = FullQueueView(radio, page=0)
        await respond(interaction, view=view) # delete_after is None by default for windows
