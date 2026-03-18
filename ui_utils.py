import discord
import aiohttp
import io

def format_duration(seconds: int):
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

async def safe_delete_message(message: discord.Message | None):
    if not message:
        return
    try:
        await message.delete()
    except:
        pass

async def safe_fetch_message(channel, message_id: int | None):
    if not message_id:
        return None
    try:
        return await channel.fetch_message(message_id)
    except:
        return None


