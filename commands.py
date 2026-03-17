import discord
from discord import app_commands
from typing import Optional
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from ui_translate import t

def setup_commands(tree: app_commands.CommandTree, radio):
    @tree.command(name="play", description="Zene lejátszása YouTube/SoundCloud linkről vagy szünet feloldása")
    @app_commands.describe(url="YouTube vagy SoundCloud URL (elhagyható a folytatáshoz)")
    async def play(interaction: discord.Interaction, url: Optional[str] = None):
        if not interaction.user.voice:
            await interaction.response.send_message(t("no_permission"), ephemeral=True)
            return

        if not url:
            if radio.status == RadioStatusEnum.PAUSED:
                radio.dispatch(RadioAction.REPLAY, user=interaction.user)
                await interaction.response.send_message(t("resuming_feedback"), ephemeral=True)
            else:
                await interaction.response.send_message(t("nothing_playing"), ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        url_strip = url.strip()
        
        if radio.voice_channel_id is None:
            radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
            
        radio.dispatch(RadioAction.ADD_EXT_LINK, url_strip, user=interaction.user)
        await interaction.followup.send(t("weblink_added"), ephemeral=True)

    @tree.command(name="pause", description="Zene szüneteltetése")
    async def pause(interaction: discord.Interaction):
        if radio.status == RadioStatusEnum.PLAYING:
            radio.dispatch(RadioAction.PAUSE, user=interaction.user)
            await interaction.response.send_message(t("pausing"), ephemeral=True)
        else:
            await interaction.response.send_message(t("cannot_pause_stopped"), ephemeral=True)

    @tree.command(name="stop", description="Zene leállítása (csatornában marad)")
    async def stop(interaction: discord.Interaction):
        radio.dispatch(RadioAction.STOP, user=interaction.user)
        await interaction.response.send_message(t("stopping"), ephemeral=True)

    @tree.command(name="disconnect", description="Lecsatlakozás és kilépés a csatornáról")
    async def disconnect(interaction: discord.Interaction):
        radio.dispatch(RadioAction.DISCONNECT, user=interaction.user)
        await interaction.response.send_message(t("severing"), ephemeral=True)

    @tree.command(name="skip", description="Aktuális szám átugrása")
    async def skip(interaction: discord.Interaction):
        if not radio.queue:
            await interaction.response.send_message(t("no_next_track"), ephemeral=True)
            return
        radio.dispatch(RadioAction.SKIP, user=interaction.user)
        await interaction.response.send_message(t("forwarding"), ephemeral=True)

    @tree.command(name="back", description="Visszalépés az előző számra")
    async def back(interaction: discord.Interaction):
        if not radio.history:
            await interaction.response.send_message(t("no_prev_track"), ephemeral=True)
            return
        radio.dispatch(RadioAction.BACK, user=interaction.user)
        await interaction.response.send_message(t("back_label") + "...", ephemeral=True)

    @tree.command(name="join", description="Csatlakozás a hangcsatornádhoz")
    async def join(interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message(t("no_permission"), ephemeral=True)
            return
        radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
        await interaction.response.send_message(f"{t('syncing')} ({interaction.user.voice.channel.name})", ephemeral=True)

    @tree.command(name="volume", description="Hangerő beállítása (0-100)")
    @app_commands.describe(percent="Százalék (0-100)")
    async def volume(interaction: discord.Interaction, percent: int):
        if 0 <= percent <= 100:
            radio.dispatch(RadioAction.SET_VOLUME, percent / 100, user=interaction.user)
            await interaction.response.send_message(f"{t('vol_set')} {percent}%", ephemeral=True)
        else:
            await interaction.response.send_message(t("vol_range_error"), ephemeral=True)

    @tree.command(name="seek", description="Ugrás egy adott időponthoz")
    @app_commands.describe(time="Időpont (pl. 1:30 vagy másodperc)")
    async def seek(interaction: discord.Interaction, time: str):
        if radio.status in [RadioStatusEnum.IDLE, RadioStatusEnum.STOPPED]:
            await interaction.response.send_message(t("cannot_seek_stopped"), ephemeral=True)
            return

        if not radio.current_song:
            await interaction.response.send_message(t("no_current_track"), ephemeral=True)
            return
            
        try:
            parts = time.split(":")
            if len(parts) == 2:
                minutes, seconds = map(int, parts)
                total_seconds = minutes * 60 + seconds
            else:
                total_seconds = int(time)
        except:
            await interaction.response.send_message(t("format_error"), ephemeral=True)
            return

        radio.dispatch(RadioAction.SEEK, total_seconds, user=interaction.user)
        await interaction.response.send_message(f"{t('jumping')} {time}", ephemeral=True)

    @tree.command(name="queue", description="Várólista megtekintése")
    async def queue(interaction: discord.Interaction):
        from ui_search import FullQueueView
        view = FullQueueView(radio, page=0)
        await interaction.response.send_message(view=view, ephemeral=True)
