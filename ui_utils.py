import discord
import os
import aiohttp
import io
from PIL import Image

def format_duration(seconds: int):
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

def fixed(text: str, length: int = 42):
    text = str(text)
    if len(text) > length:
        return text[:length - 3] + "..."
    return text.ljust(length)

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

async def get_dominant_color(url, size=40):
    """Extracts the most dominant color from a URL (thumbnail)."""
    try:
        if not url or not url.startswith(('http://', 'https://')):
            return None
            
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    img_data = io.BytesIO(await resp.read())
                    with Image.open(img_data) as img:
                        img = img.convert("RGB")
                        img = img.resize((size, size))
                        quantized = img.quantize(colors=8, method=Image.Quantize.MAXCOVERAGE)
                        palette = quantized.getpalette()
                        color_counts = quantized.getcolors()
                        
                        if not color_counts:
                            return None
                            
                        most_frequent = max(color_counts, key=lambda x: x[0])[1]
                        r = palette[most_frequent * 3]
                        g = palette[most_frequent * 3 + 1]
                        b = palette[most_frequent * 3 + 2]
                        
                        return (r << 16) | (g << 8) | b
        return None
    except:
        return None
