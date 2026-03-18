import discord
from discord import app_commands
from typing import Optional
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from ui_translate import t

def setup_commands(tree: app_commands.CommandTree, radio):
    @tree.interaction_check
    async def restricted_channel_check(interaction: discord.Interaction) -> bool:
        # Check if limited to a specific channel
        if interaction.channel_id != radio.config.radio_text_channel_id:
            return False
        return True

    @tree.command(name="play", description=t("help_play_desc"))
    @app_commands.describe(url=t("search_placeholder"))
    async def play(interaction: discord.Interaction, url: Optional[str] = None):
        if not interaction.user.voice:
            await interaction.response.send_message(t("no_permission"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return

        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return

        if not url:
            if radio.status == RadioStatusEnum.PAUSED:
                radio.dispatch(RadioAction.REPLAY, user=interaction.user)
                await interaction.response.send_message(t("resuming_feedback"), ephemeral=True)
            else:
                await interaction.response.send_message(t("nothing_playing"), ephemeral=True)
            
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
            
        await interaction.response.defer(ephemeral=True)
        url_strip = url.strip()
        
        if radio.voice_channel_id is None:
            radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
            
        radio.dispatch(RadioAction.ADD_EXT_LINK, url_strip, user=interaction.user)
        await interaction.followup.send(t("weblink_added"), ephemeral=True)
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))

    @tree.command(name="pause", description=t("help_pause_desc"))
    async def pause(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return

        if radio.status == RadioStatusEnum.PLAYING:
            radio.dispatch(RadioAction.PAUSE, user=interaction.user)
            await interaction.response.send_message(t("pausing"), ephemeral=True)
        else:
            await interaction.response.send_message(t("cannot_pause_stopped"), ephemeral=True)
        
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))

    @tree.command(name="stop", description=t("help_stop_desc"))
    async def stop(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
        radio.dispatch(RadioAction.STOP, user=interaction.user)
        await interaction.response.send_message(t("stopping"), ephemeral=True)
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))

    @tree.command(name="disconnect", description=t("help_leave_desc"))
    async def disconnect(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            return
        radio.dispatch(RadioAction.DISCONNECT, user=interaction.user)
        await interaction.response.send_message(t("severing"), ephemeral=True)
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))

    @tree.command(name="skip", description=t("help_skip_desc"))
    async def skip(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
        if not radio.queue:
            await interaction.response.send_message(t("no_next_track"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
        radio.dispatch(RadioAction.SKIP, user=interaction.user)
        await interaction.response.send_message(t("forwarding"), ephemeral=True)
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))

    @tree.command(name="back", description=t("help_back_desc"))
    async def back(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
        if not radio.history:
            await interaction.response.send_message(t("no_prev_track"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
        radio.dispatch(RadioAction.BACK, user=interaction.user)
        await interaction.response.send_message(t("back_label") + "...", ephemeral=True)
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))

    @tree.command(name="join", description=t("help_join_desc"))
    async def join(interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message(t("no_permission"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
        
        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return

        radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
        await interaction.response.send_message(f"{t('syncing')} ({interaction.user.voice.channel.name})", ephemeral=True)
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))

    @tree.command(name="volume", description=t("help_vol_desc"))
    @app_commands.describe(percent=t("help_vol_desc"))
    async def volume(interaction: discord.Interaction, percent: int):
        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
            
        if 0 <= percent <= 100:
            radio.dispatch(RadioAction.SET_VOLUME, percent / 100, user=interaction.user)
            await interaction.response.send_message(f"{t('vol_set')} {percent}%", ephemeral=True)
        else:
            await interaction.response.send_message(t("vol_range_error"), ephemeral=True)
            
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))

    @tree.command(name="seek", description=t("help_seek_desc"))
    @app_commands.describe(time=t("help_seek_desc"))
    async def seek(interaction: discord.Interaction, time: str):
        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return

        if radio.status in [RadioStatusEnum.IDLE, RadioStatusEnum.STOPPED]:
            await interaction.response.send_message(t("cannot_seek_stopped"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
            
        if not radio.current_song:
            await interaction.response.send_message(t("no_current_track"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
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
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return

        radio.dispatch(RadioAction.SEEK, total_seconds, user=interaction.user)
        await interaction.response.send_message(f"{t('jumping')} {time}", ephemeral=True)
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))

    @tree.command(name="queue", description=t("help_queue_desc"))
    async def queue(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await interaction.response.send_message(t("not_in_same_voice"), ephemeral=True)
            from ui_utils import delayed_delete
            import asyncio
            asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
            return
        from ui_search import FullQueueView
        view = FullQueueView(radio, page=0)
        await interaction.response.send_message(view=view, ephemeral=True)
        from ui_utils import delayed_delete
        import asyncio
        asyncio.create_task(delayed_delete(interaction, radio.config.notification_timeout))
