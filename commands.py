import discord
from discord import app_commands
from typing import Optional
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from ui_translate import t
from ui_utils import respond, get_feedback
from ui_icons import Icons

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
            await respond(interaction, get_feedback("no_permission"), delete_after=radio.config.notification_timeout)
            return

        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return

        if not url:
            if radio.status == RadioStatusEnum.PAUSED:
                radio.dispatch(RadioAction.REPLAY, user=interaction.user)
                await respond(interaction, get_feedback("resuming_feedback"), delete_after=radio.config.notification_timeout)
            else:
                await respond(interaction, get_feedback("nothing_playing"), delete_after=radio.config.notification_timeout)
            return
            
        await interaction.response.defer(ephemeral=True)
        url_strip = url.strip()
        
        if radio.voice_channel_id is None:
            radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
            
        radio.dispatch(RadioAction.ADD_EXT_LINK, url_strip, user=interaction.user)
        await respond(interaction, get_feedback("weblink_added"), delete_after=radio.config.notification_timeout)

    @tree.command(name="pause", description=t("help_pause_desc"))
    async def pause(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return

        if radio.status == RadioStatusEnum.PLAYING:
            radio.dispatch(RadioAction.PAUSE, user=interaction.user)
            await respond(interaction, get_feedback("pausing"), delete_after=radio.config.notification_timeout)
        else:
            await respond(interaction, get_feedback("cannot_pause_stopped"), delete_after=radio.config.notification_timeout)

    @tree.command(name="stop", description=t("help_stop_desc"))
    async def stop(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        radio.dispatch(RadioAction.STOP, user=interaction.user)
        await respond(interaction, get_feedback("stopping"), delete_after=radio.config.notification_timeout)

    @tree.command(name="disconnect", description=t("help_leave_desc"))
    async def disconnect(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        radio.dispatch(RadioAction.DISCONNECT, user=interaction.user)
        await respond(interaction, get_feedback("severing"), delete_after=radio.config.notification_timeout)

    @tree.command(name="skip", description=t("help_skip_desc"))
    async def skip(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        if not radio.queue:
            await respond(interaction, get_feedback("no_next_track"), delete_after=radio.config.notification_timeout)
            return
        radio.dispatch(RadioAction.SKIP, user=interaction.user)
        await respond(interaction, get_feedback("forwarding"), delete_after=radio.config.notification_timeout)

    @tree.command(name="back", description=t("help_back_desc"))
    async def back(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        if not radio.history:
            await respond(interaction, get_feedback("no_prev_track"), delete_after=radio.config.notification_timeout)
            return
        radio.dispatch(RadioAction.BACK, user=interaction.user)
        await respond(interaction, get_feedback("backing"), delete_after=radio.config.notification_timeout)

    @tree.command(name="join", description=t("help_join_desc"))
    async def join(interaction: discord.Interaction):
        if not interaction.user.voice:
            await respond(interaction, get_feedback("no_permission"), delete_after=radio.config.notification_timeout)
            return
        
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return

        radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)
        feedback = f"{get_feedback('syncing')} ({interaction.user.voice.channel.name})"
        await respond(interaction, feedback, delete_after=radio.config.notification_timeout)

    @tree.command(name="volume", description=t("help_vol_desc"))
    @app_commands.describe(percent=t("help_vol_desc"))
    async def volume(interaction: discord.Interaction, percent: int):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
            
        if 0 <= percent <= 100:
            radio.dispatch(RadioAction.SET_VOLUME, percent / 100, user=interaction.user)
            feedback = f"{get_feedback('vol_set')} {percent}%"
            await respond(interaction, feedback, delete_after=radio.config.notification_timeout)
        else:
            await respond(interaction, get_feedback("vol_range_error"), delete_after=radio.config.notification_timeout)

    @tree.command(name="seek", description=t("help_seek_desc"))
    @app_commands.describe(time=t("help_seek_desc"))
    async def seek(interaction: discord.Interaction, time: str):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return

        if radio.status in [RadioStatusEnum.IDLE, RadioStatusEnum.STOPPED]:
            await respond(interaction, get_feedback("cannot_seek_stopped"), delete_after=radio.config.notification_timeout)
            return
            
        if not radio.current_song:
            await respond(interaction, get_feedback("no_current_track"), delete_after=radio.config.notification_timeout)
            return
            
        try:
            parts = time.split(":")
            if len(parts) == 2:
                minutes, seconds = map(int, parts)
                total_seconds = minutes * 60 + seconds
            else:
                total_seconds = int(time)
        except:
            await respond(interaction, get_feedback("format_error"), delete_after=radio.config.notification_timeout)
            return

        radio.dispatch(RadioAction.SEEK, total_seconds, user=interaction.user)
        feedback = f"{get_feedback('jumping')} {time}"
        await respond(interaction, feedback, delete_after=radio.config.notification_timeout)

    @tree.command(name="queue", description=t("help_queue_desc"))
    async def queue(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        from ui_search import FullQueueView
        view = FullQueueView(radio, page=0, user=interaction.user)
        await respond(interaction, view=view) # delete_after is None by default for windows

    @tree.command(name="loop", description=t("help_loop_desc"))
    async def loop(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
            
        radio.dispatch(RadioAction.LOOP, user=interaction.user)
        msg_key = "loop_enabled" if not radio.loop_mode else "loop_disabled"
        await respond(interaction, get_feedback(msg_key), delete_after=radio.config.notification_timeout)

    @tree.command(name="loopq", description=t("help_loopq_desc"))
    async def loopq(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
            
        radio.dispatch(RadioAction.LOOP_QUEUE, user=interaction.user)
        msg_key = "loop_queue_enabled" if not radio.loop_queue_mode else "loop_queue_disabled"
        await respond(interaction, get_feedback(msg_key), delete_after=radio.config.notification_timeout)

    @tree.command(name="shuffle", description=t("help_shuffle_desc"))
    async def shuffle(interaction: discord.Interaction):
        if not radio.can_interact(interaction.user):
            await respond(interaction, get_feedback("not_in_same_voice"), delete_after=radio.config.notification_timeout)
            return
        radio.dispatch(RadioAction.SHUFFLE, user=interaction.user)
        await respond(interaction, get_feedback("queue_shuffled"), delete_after=radio.config.notification_timeout)

    @tree.command(name="clearcache", description="Clears the local audio cache (Admin only)")
    async def clear_cache(interaction: discord.Interaction):
        if not radio.is_admin(interaction.user):
            await respond(interaction, get_feedback("admin_only"), ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        count = radio.clear_cache()
        await respond(interaction, f"Cache cleared: {count} files removed.", ephemeral=True)

async def handle_prefix_commands(message: discord.Message, radio):
    """Processes traditional ! prefix commands."""
    if message.author.bot or not message.content:
        return

    config = radio.config
    # Restricted to radio channel
    if message.channel.id != config.radio_text_channel_id:
        return

    prefix = config.command_prefix
    if not message.content.startswith(prefix):
        return

    # Simple parser
    content = message.content[len(prefix):].strip()
    if not content:
        return

    parts = content.split()
    command = parts[0].lower()
    args = parts[1:]

    from logger import log
    import asyncio

    async def delayed_delete(msg):
        await asyncio.sleep(config.command_delete_delay)
        try:
            await msg.delete()
        except discord.Forbidden:
            log.warning(f"Could not delete message from {msg.author}: Missing 'Manage Messages' permission.")
        except:
            pass

    try:
        # Start deletion in background with delay
        asyncio.create_task(delayed_delete(message))

        if command in ["play", "p"]:
            if not message.author.voice:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_permission"), delete_after=config.notification_timeout)
            else:
                query = " ".join(args).strip() if args else None
                if not query:
                    if radio.status == RadioStatusEnum.PAUSED:
                        radio.dispatch(RadioAction.REPLAY, user=message.author)
                    else:
                        await message.channel.send(f"{message.author.mention} " + get_feedback("nothing_playing"), delete_after=config.notification_timeout)
                else:
                    if radio.voice_channel_id is None:
                        radio.dispatch(RadioAction.JOIN, message.author.voice.channel.id, user=message.author)
                    radio.dispatch(RadioAction.ADD_EXT_LINK, query, user=message.author)
                    await message.channel.send(f"{message.author.mention} " + get_feedback("weblink_added"), delete_after=config.notification_timeout)

        elif command == "stop":
            radio.dispatch(RadioAction.STOP, user=message.author)
            await message.channel.send(f"{message.author.mention} " + get_feedback("stopping"), delete_after=config.notification_timeout)

        elif command in ["disconnect", "leave", "d", "l"]:
            radio.dispatch(RadioAction.DISCONNECT, user=message.author)
            await message.channel.send(f"{message.author.mention} " + get_feedback("severing"), delete_after=config.notification_timeout)

        elif command in ["skip", "s"]:
            if radio.queue:
                radio.dispatch(RadioAction.SKIP, user=message.author)
                await message.channel.send(f"{message.author.mention} " + get_feedback("forwarding"), delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_next_track"), delete_after=config.notification_timeout)

        elif command in ["back", "b"]:
            if radio.history:
                radio.dispatch(RadioAction.BACK, user=message.author)
                await message.channel.send(f"{message.author.mention} " + get_feedback("back_label") + "...", delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_prev_track"), delete_after=config.notification_timeout)

        elif command in ["join", "j"]:
            if message.author.voice:
                radio.dispatch(RadioAction.JOIN, message.author.voice.channel.id, user=message.author)
                feedback = f"{get_feedback('syncing')} ({message.author.voice.channel.name})"
                await message.channel.send(f"{message.author.mention} " + feedback, delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_permission"), delete_after=config.notification_timeout)

        elif command in ["volume", "v"] and args:
            try:
                vol = int(args[0])
                if 0 <= vol <= 100:
                    radio.dispatch(RadioAction.SET_VOLUME, vol / 100, user=message.author)
                else:
                    await message.channel.send(f"{message.author.mention} " + get_feedback("vol_range_error"), delete_after=config.notification_timeout)
            except:
                await message.channel.send(f"{message.author.mention} " + get_feedback("invalid_number"), delete_after=config.notification_timeout)

        elif command in ["loop", "lt"]:
            # Check if 'l' is leave or loop. Leave was defined as 'l' at line 218.
            # I'll use 'loop' for loop and leave 'l' for leave to avoid breaking legacy?
            # User said "loop a számot", so maybe just 'loop'.
            radio.dispatch(RadioAction.LOOP, user=message.author)
            await message.channel.send(f"{message.author.mention} {get_feedback('loop_toggle')}", delete_after=config.notification_timeout)

        elif command in ["loopq", "lq"]:
            radio.dispatch(RadioAction.LOOP_QUEUE, user=message.author)
            await message.channel.send(f"{message.author.mention} {get_feedback('loop_queue_toggle')}", delete_after=config.notification_timeout)

        elif command in ["shuffle", "sh"]:
            radio.dispatch(RadioAction.SHUFFLE, user=message.author)
            await message.channel.send(f"{message.author.mention} {get_feedback('queue_shuffled')}", delete_after=config.notification_timeout)

        elif command in ["queue", "q"]:
            from ui_search import FullQueueView
            view = FullQueueView(radio, page=0, user=message.author)
            await message.channel.send(view=view, delete_after=config.view_timeout)

        elif command in ["help", "h"]:
            from ui_player import HelpView
            view = HelpView(radio)
            await message.channel.send(embed=view.get_embed(), delete_after=config.view_timeout)

        elif command == "restart":
            if radio.is_admin(message.author):
                feedback = f"{get_feedback('restarting')}"
                await message.channel.send(f"{message.author.mention} {feedback}")
                radio.dispatch(RadioAction.RESTART, user=message.author)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("admin_only"), delete_after=5)

        elif command == "clearcache":
            if radio.is_admin(message.author):
                count = radio.clear_cache()
                await message.channel.send(f"{message.author.mention} Cache cleared: {count} files removed.", delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("admin_only"), delete_after=config.notification_timeout)

        elif command == "seek" and args:
            if radio.current_song:
                ts = args[0]
                try:
                    parts_ts = ts.split(":")
                    if len(parts_ts) == 2:
                        total = int(parts_ts[0]) * 60 + int(parts_ts[1])
                    else:
                        total = int(ts)
                    radio.dispatch(RadioAction.SEEK, total, user=message.author)
                    await message.channel.send(f"{message.author.mention} " + f"{t('jumping')} {ts}", delete_after=config.notification_timeout)
                except:
                    await message.channel.send(f"{message.author.mention} " + get_feedback("format_error"), delete_after=config.notification_timeout)
            else:
                await message.channel.send(f"{message.author.mention} " + get_feedback("no_current_track"), delete_after=config.notification_timeout)

    except Exception as e:
        log.error(f"Error in prefix command {command}: {e}")
