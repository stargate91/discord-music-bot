import asyncio
import discord
import sys
import os
import argparse
import random

# 1. Parse instance arguments before importing project modules
parser = argparse.ArgumentParser(description="Discord Radio Bot Instance")
parser.add_argument("instance", nargs="?", default="", help="Name of this bot instance (e.g. bot1)")
parser.add_argument("--config", help="Specific config file path")
args = parser.parse_args()

# 2. Set environment variable for logger/state discovery
if args.instance:
    os.environ["INSTANCE_NAME"] = args.instance

# 3. Import project modules after setting environment
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
    # Determine config file name
    config_file = args.config if args.config else (f"config{args.instance}.json" if args.instance else "config.json")
    
    try:
        config = load_config(config_file, instance_name=args.instance)
        
        # Initialize Icons from config
        from ui_icons import Icons
        Icons.setup(config)

        # Initialize Logging
        from logger import setup_logging
        setup_logging(config.log_level)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    bot = discord.Client(intents=intents)
    tree = app_commands.CommandTree(bot)
    
    radio = RadioManager(config)
    
    # Clear cache on startup if ephemeral cache is enabled
    if config.ephemeral_cache:
        log.info("[CACHE] Ephemeral cache enabled. Performing startup cleanup...")
        radio.clear_cache()
    
    # Initialize UI Manager (Replacement for global init_ui)
    ui_manager = UIManager(bot, config, radio)
    
    # Initialize Player Engine
    player_instance = RadioPlayer(
        bot, config, radio, 
        update_ui_callback=ui_manager.update_now_playing, 
        refresh_ui_callback=ui_manager.refresh_all_uis, 
        cleanup_ui_callback=ui_manager.force_new_embed
    )
    
    # Clear global commands from this bot identity to prevent crossover
    # DO THIS BEFORE setup_commands adds new ones
    tree.clear_commands(guild=None)
    
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

    bg_tasks = []

    @bot.event
    async def on_ready():
        log.info(f"--- RADIO BOT ONLINE ---")
        log.info(f"Identity: {bot.user} (ID: {bot.user.id})")
        log.info(f"Instance: {args.instance if args.instance else 'Default'}")
        log.info(f"------------------------")
        try:
            # Re-register views for persistence
            bot.add_view(WelcomeLayout(radio))
            bot.add_view(FrequencyStationView(radio))
            bot.add_view(NowPlayingView(radio))
            await ui_manager.force_new_embed()
        except Exception as e:
            log.error(f"Error during on_ready: {e}")

        # [Slash sync logic]
        try:
            guild_id = config.guild_id
            if guild_id and guild_id > 0:
                target_guild = discord.Object(id=guild_id)
                tree.copy_global_to(guild=target_guild)
                if args.instance:
                    # Jitter sync to avoid rate limits with multiple instances
                    await asyncio.sleep(random.uniform(1.0, 5.0))
                await tree.sync(guild=target_guild)
                log.info(f"Slash commands synced to guild: {guild_id}")
            else:
                if args.instance:
                    await asyncio.sleep(random.uniform(1.0, 5.0))
                await tree.sync()
                log.info("Slash commands synced globally!")
        except Exception as e:
            log.error(f"Failed to sync commands: {e}")
            
        # Optional Auto-Join [and jitter added in previous step]
        if config.auto_join_channel_id > 0:
            try:
                channel = bot.get_channel(config.auto_join_channel_id)
                if not channel:
                    channel = await bot.fetch_channel(config.auto_join_channel_id)
                
                if channel and isinstance(channel, discord.VoiceChannel):
                    if not channel.guild.voice_client:
                        log.info(f"Auto-joining channel: {channel.name}")
                        if args.instance:
                            await asyncio.sleep(random.uniform(0.5, 3.0))
                        await channel.connect(reconnect=True, timeout=20.0, self_deaf=True)
                        radio.voice_channel_id = channel.id
                        radio.voice = channel.guild.voice_client
                        radio.status = RadioStatusEnum.IDLE
            except Exception as e:
                log.error(f"Auto-join failed: {e}")

        # Start Background tasks and store them for cleanup
        if not radio.task:
            radio.task = bot.loop.create_task(player_instance.run_loop())
            bg_tasks.append(radio.task)
        
        bg_tasks.append(bot.loop.create_task(embed_refresh_loop()))
        bg_tasks.append(bot.loop.create_task(progress_update_loop()))

    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id == bot.user.id:
            target_channel = after.channel
            old_channel = before.channel
            
            # Check if we are still actually connected to some voice client in the guild
            guild = member.guild
            voice_client = guild.voice_client
            
            if target_channel:
                if old_channel and old_channel.id != target_channel.id:
                    # Clear status of the old channel if we moved
                    await ui_manager.clear_voice_status(old_channel.id)
                    
                if not old_channel or old_channel.id != target_channel.id:
                    radio.voice_channel_id = target_channel.id
                    radio.voice = voice_client
                    await ui_manager.update_now_playing(radio.current_song)
            else:
                # We got a disconnect event. Only clear state if we ARE actually disconnected.
                # Sometimes Discord sends transient None channels while switching or blips.
                if not voice_client or not voice_client.is_connected():
                    # Small delay to allow for transient blips / reconnects
                    await asyncio.sleep(1.5)
                    voice_client = member.guild.voice_client 
                    
                    if not voice_client or not voice_client.is_connected():
                        log.info(f"[VOICE] Confirmed disconnect for {member.guild.name}. Cleaning up state.")
                        prev_channel_id = old_channel.id if old_channel else radio.voice_channel_id
                        radio.voice_channel_id = None
                        radio.voice = None
                        radio.status = RadioStatusEnum.IDLE
                        radio.current_song = None
                        await ui_manager.update_now_playing(None)
                        
                        if prev_channel_id:
                            await ui_manager.clear_voice_status(prev_channel_id)
                    else:
                        log.info(f"[VOICE] Disconnect event was transient. Bot is still connected to {voice_client.channel.name}")

    @bot.event
    async def on_interaction(interaction: discord.Interaction):
        await tree.process_commands(interaction)

    @bot.event
    async def on_message(message: discord.Message):
        from commands import handle_prefix_commands
        await handle_prefix_commands(message, radio)

    try:
        async with bot:
            await bot.start(config.token)
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("Shutdown initiated...")
    finally:
        # Gracefully cancel all tracked background tasks
        log.info(f"Cleaning up {len(bg_tasks)} background tasks...")
        for task in bg_tasks:
            if not task.done():
                task.cancel()
        
        if bg_tasks:
            # Shield to allow cancellation to propagate
            await asyncio.gather(*bg_tasks, return_exceptions=True)
        
        if not bot.is_closed():
            await bot.close()
        log.info("Shutdown complete.")

        if os.getenv("BOT_RESTART") == "1":
            log.info("Process restart initiated via execv...")
            os.environ["BOT_RESTART"] = "0"
            os.execv(sys.executable, [sys.executable] + sys.argv)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
