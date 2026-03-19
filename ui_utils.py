import discord
import asyncio
from logger import log

async def delayed_delete(item: discord.Message | discord.Interaction | None, delay: float = 20.0):
    if not item:
        return
    
    await asyncio.sleep(delay)
    try:
        if isinstance(item, discord.Interaction):
            await item.delete_original_response()
        elif isinstance(item, discord.Message):
            await item.delete()
    except:
        # Fails silent if already deleted or expired
        pass

async def respond(interaction: discord.Interaction, content=None, embed=None, view=None, ephemeral=True, delete_after: float | None = None):
    """
    Modularized interaction responder. 
    Handles both initial response and followup automatically.
    If delete_after is provided, the message will be scheduled for deletion.
    """
    kwargs = {"ephemeral": ephemeral}
    if content is not None:
        kwargs["content"] = content
    if embed is not None:
        kwargs["embed"] = embed
    if view is not None:
        kwargs["view"] = view
    
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(**kwargs)
            target = interaction
        else:
            msg = await interaction.followup.send(**kwargs)
            target = msg
            
        if delete_after:
            asyncio.create_task(delayed_delete(target, delete_after))
    except Exception as e:
        log.error(f"UI Respond error: {e}")

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


