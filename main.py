import asyncio
import discord
from discord import app_commands
from config_loader import load_config
from ui import UIManager
from ui_player import WelcomeLayout, FrequencyStationView, NowPlayingView
from core.radio import RadioManager
from player_engine import RadioPlayer
from radio_actions import RadioAction, RadioState as RadioStatusEnum
from logger import log
from commands import setup_commands
from ui_translate import t

async def main():
    config = load_config()
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    bot = discord.Client(intents=intents)
    tree = app_commands.CommandTree(bot)
    
    radio = RadioManager(config)
    
    # Initialize UI Manager (Replacement for global init_ui)
    ui_manager = UIManager(bot, config, radio)
    
    # Initialize Player Engine
    player_instance = RadioPlayer(
        bot, config, radio, 
        update_ui_callback=ui_manager.update_now_playing, 
        refresh_ui_callback=ui_manager.refresh_all_uis, 
        cleanup_ui_callback=ui_manager.force_new_embed
    )
    
    setup_commands(tree, radio)

    async def embed_refresh_loop():
        await bot.wait_until_ready()
        while not bot.is_closed():
            await asyncio.sleep(config.embed_refresh_minutes * 60)
            await ui_manager.force_new_embed()

    async def progress_update_loop():
        await bot.wait_until_ready()
        while not bot.is_closed():
            await asyncio.sleep(config.progress_update_seconds)
            if radio.status == RadioStatusEnum.PLAYING and radio.now_playing_message:
                try:
                    await ui_manager.update_now_playing(radio.current_song)
                except:
                    pass

    @bot.event
    async def on_ready():
        log.info(f"Online as: {bot.user}")
        try:
            # Re-register views for persistence
            bot.add_view(WelcomeLayout(radio))
            bot.add_view(FrequencyStationView(radio))
            bot.add_view(NowPlayingView(radio))
            await ui_manager.force_new_embed()
        except Exception as e:
            log.error(f"Error during on_ready: {e}")

        # Sync Slash Commands
        try:
            guild_id = config.guild_id
            if guild_id and guild_id > 0:
                target_guild = discord.Object(id=guild_id)
                tree.copy_global_to(guild=target_guild)
                await tree.sync(guild=target_guild)
                log.info(f"Slash commands synced to guild: {guild_id}")
            else:
                await tree.sync()
                log.info("Slash commands synced globally!")
        except Exception as e:
            log.error(f"Failed to sync commands: {e}")
            
        # Optional Auto-Join
        if config.auto_join_channel_id > 0:
            try:
                channel = bot.get_channel(config.auto_join_channel_id)
                if not channel:
                    channel = await bot.fetch_channel(config.auto_join_channel_id)
                
                if channel and isinstance(channel, discord.VoiceChannel):
                    if not channel.guild.voice_client:
                        log.info(f"Auto-joining channel: {channel.name}")
                        await channel.connect()
                        radio.voice_channel_id = channel.id
                        radio.voice = channel.guild.voice_client
                        radio.status = RadioStatusEnum.IDLE
            except Exception as e:
                log.error(f"Auto-join failed: {e}")

        # Start Background tasks
        if not radio.task:
            radio.task = bot.loop.create_task(player_instance.run_loop())
        bot.loop.create_task(embed_refresh_loop())
        bot.loop.create_task(progress_update_loop())

    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id == bot.user.id:
            target_channel = after.channel
            old_channel = before.channel
            
            # Check if we are still actually connected to some voice client in the guild
            guild = member.guild
            voice_client = guild.voice_client
            
            if target_channel:
                if not old_channel or old_channel.id != target_channel.id:
                    radio.voice_channel_id = target_channel.id
                    radio.voice = voice_client
                    await ui_manager.update_now_playing(radio.current_song)
            else:
                # We got a disconnect event. Only clear state if we ARE actually disconnected.
                # Sometimes Discord sends transient None channels while switching.
                if not voice_client or not voice_client.is_connected():
                    radio.voice_channel_id = None
                    radio.voice = None
                    radio.status = RadioStatusEnum.IDLE
                    radio.current_song = None
                    await ui_manager.update_now_playing(None)

    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot or not message.content:
            return

        prefix = "!" # You can make this configurable
        if not message.content.startswith(prefix):
            return

        # Simple parser
        content = message.content[len(prefix):].strip()
        if not content:
            return

        parts = content.split()
        command = parts[0].lower()
        args = parts[1:]

        handled = False
        
        async def delayed_delete(msg):
            await asyncio.sleep(1.5) # Wait a bit so the user sees it "worked"
            try:
                await msg.delete()
            except discord.Forbidden:
                log.warning(f"Could not delete message from {msg.author}: Missing 'Manage Messages' permission.")
            except:
                pass

        try:
            # Start deletion in background with delay
            asyncio.create_task(delayed_delete(message))

            if command == "play":
                if not message.author.voice:
                    await message.channel.send(f"{message.author.mention} " + t("no_permission"), delete_after=5)
                else:
                    url = args[0] if args else None
                    if not url:
                        if radio.status == RadioStatusEnum.PAUSED:
                            radio.dispatch(RadioAction.REPLAY, user=message.author)
                        else:
                            await message.channel.send(f"{message.author.mention} " + t("nothing_playing"), delete_after=5)
                    else:
                        if radio.voice_channel_id is None:
                            radio.dispatch(RadioAction.JOIN, message.author.voice.channel.id, user=message.author)
                        radio.dispatch(RadioAction.ADD_EXT_LINK, url.strip(), user=message.author)

            elif command == "stop":
                radio.dispatch(RadioAction.STOP, user=message.author)

            elif command == "disconnect" or command == "leave":
                radio.dispatch(RadioAction.DISCONNECT, user=message.author)

            elif command == "skip":
                if radio.queue:
                    radio.dispatch(RadioAction.SKIP, user=message.author)
                else:
                    await message.channel.send(f"{message.author.mention} " + t("no_next_track"), delete_after=5)

            elif command == "back":
                if radio.history:
                    radio.dispatch(RadioAction.BACK, user=message.author)
                else:
                    await message.channel.send(f"{message.author.mention} " + t("no_prev_track"), delete_after=5)

            elif command == "join":
                if message.author.voice:
                    radio.dispatch(RadioAction.JOIN, message.author.voice.channel.id, user=message.author)
                else:
                    await message.channel.send(f"{message.author.mention} " + t("no_permission"), delete_after=5)

            elif command == "volume" and args:
                try:
                    vol = int(args[0])
                    if 0 <= vol <= 100:
                        radio.dispatch(RadioAction.SET_VOLUME, vol / 100, user=message.author)
                    else:
                        await message.channel.send(f"{message.author.mention} " + t("vol_range_error"), delete_after=5)
                except:
                    await message.channel.send(f"{message.author.mention} " + t("invalid_number"), delete_after=5)

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
                    except:
                        await message.channel.send(f"{message.author.mention} " + t("format_error"), delete_after=5)
                else:
                    await message.channel.send(f"{message.author.mention} " + t("no_current_track"), delete_after=5)
            
            elif command == "queue":
                from ui_search import FullQueueView
                view = FullQueueView(radio, page=0)
                await message.channel.send(view=view, delete_after=60)

        except Exception as e:
            log.error(f"Error in prefix command {command}: {e}")

    async with bot:
        await bot.start(config.token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
