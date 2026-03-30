import discord
import asyncio
from ui_icons import Icons
from ui_translate import t
from logger import log

# This function waits for a specific amount of time (default is 20 seconds)
# and then deletes the message or the interaction response. 
# We use this for temporary "ephemeral-like" messages that should disappear.
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
        # We don't care if it fails (maybe the message was already deleted by someone else)
        pass

# This is a very important function! 
# It takes a translation key (like "now_playing"), finds the right icon for it, 
# and returns a nice string like "🎧 NOW PLAYING".
def get_feedback(key: str, **kwargs) -> str:
    """
    Returns a translated string prefixed with the appropriate emoji.
    """
    icons_map = {
        # --- Errors & Warnings (We use warning icon for these) ---
        "not_in_same_voice": Icons.WARNING,      # User is in a different voice channel
        "no_permission": Icons.WARNING,          # Bot doesn't have rights to join
        "admin_only": Icons.WARNING,             # Only admins can do this
        "error_generic": Icons.WARNING,          # Something went wrong generally
        "cannot_pause_stopped": Icons.WARNING,   # Music is already stopped, can't pause
        "cannot_seek_stopped": Icons.WARNING,    # Can't jump to time if music is not playing
        "vol_range_error": Icons.WARNING,        # Volume must be between 0 and 100
        "no_current_track": Icons.WARNING,       # No song playing to jump in
        "no_next_track": Icons.WARNING,          # End of the queue
        "no_prev_track": Icons.WARNING,          # No history to go back to
        "format_error": Icons.WARNING,           # Wrong time format (should be mm:ss)
        "too_long": Icons.WARNING,               # Timestamp is longer than the song
        "cooldown_error": Icons.WARNING,         # Clicking too fast, system needs a rest
        "nothing_playing": Icons.WARNING,        # Player is empty
        "invalid_number": Icons.WARNING,         # Not a valid number given
        "empty": Icons.WARNING,                  # List is empty
        "error_resolve": Icons.WARNING,          # Could not process the link
        
        # --- Status Messages (Shown in the player header) ---
        "now_playing": Icons.HEADPHONES,         # Music is currently playing
        "paused": Icons.PAUSE,                   # Music is paused
        "stopped": Icons.STOP,                   # Music is stopped
        "buffering": Icons.BUFFERING,           # Loading the song from the internet
        "idle": Icons.IDLE,                      # Bot is waiting for songs
        "idle_status": Icons.IDLE,               # Detailed waiting message
        "resolving_link": "",                    # Trying to understand what the link is
        
        # --- Headers / Titles (Used as section titles) ---
        "help_title": Icons.HELP,                 # The help window title
        "search_results_title": Icons.SEARCH,     # Title for search results list
        "library_label": Icons.FOLDER_HEART,      # Favorites folder title
        "history_label": Icons.HISTORY,           # Recently played songs title
        "queue_label": Icons.QUEUE,               # Upcoming songs title
        "system_sync": Icons.SYNC,               # Connection screen header
        "system_settings": Icons.GEAR,           # Settings screen header
        "standby_mode": Icons.STANDBY,           # Standby screen header
        
        # --- Field Labels (Labels for song info, no icons requested here) ---
        "uploader": "",                          # Who uploaded the song (Artist/Channel)
        "title": "",                             # The name of the song
        "duration": "",                          # How long the song is
        "source": "",                            # Platform (YouTube/SoundCloud)
        "tuned_by": "",                          # Who requested the song
        "unknown": "",                           # Used when metadata is missing
        
        # --- Processing / Waiting (Active tasks) ---
        "search_processing": Icons.SEARCH,       # Currently looking on YouTube
        "syncing": Icons.SYNC,                   # Connecting to voice channel
        "severing": Icons.CLOSE,                 # Leaving the voice channel
        "resuming": Icons.PLAY,                  # Continuing the music
        "forwarding": Icons.NEXT,                # Moving to the next song
        "backing": Icons.BACK,                   # Moving back to the previous song
        "jumping": Icons.SEEK,                   # Moving to a specific time
        "restarting": Icons.SYNC,                # Bot is rebooting
        
        # --- Success / Confirmation (Positive feedback) ---
        "weblink_added": Icons.SUCCESS,          # Link successfully added to list
        "vol_set": Icons.SUCCESS,               # Volume changed successfully
        "added_to_fav": Icons.HEART_PLUS,        # Song added to favorites
        "removed_from_fav": Icons.HEART_MINUS,   # Song removed from favorites
        "added_all_to_queue": Icons.SUCCESS,     # All songs from a list added
        "cleared_favorites": Icons.SWEEP,        # Favorites list wiped clean
        "cleared_history": Icons.SWEEP,          # History list wiped clean
        "queue_shuffled": Icons.SWEEP,           # Queue order randomized
        "resuming_feedback": Icons.PLAY,         # Confirmation that music resumed
        "pausing": Icons.PAUSE,                  # Confirmation that it's paused
        "stopping": Icons.STOP,                  # Confirmation that it's stopped
        "loop_enabled": Icons.REPEAT,            # Single song repeat is on
        "loop_disabled": Icons.SUCCESS,          # Single song repeat is off
        "loop_queue_enabled": Icons.REPEAT,      # Whole queue repeat is on
        "loop_queue_disabled": Icons.SUCCESS,    # Whole queue repeat is off
    }
    
    emoji = icons_map.get(key, "")
    text = t(key, **kwargs)
    
    if not text:
        log.warning(f"[UI] Missing translation key for feedback: {key}")
        return f"{emoji} {key}".strip()
        
    return f"{emoji} {text}".strip()

# This is a general "send message" helper. 
# It checks if we already sent a message or if we should send a new one.
# It also handles ephemeral (private) messages and auto-deletion.
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
            # This is the first time we reply to this specific command/button click
            await interaction.response.send_message(**kwargs)
            target = interaction
        else:
            # We already replied once (e.g. with a defer), so we send a followup
            msg = await interaction.followup.send(**kwargs)
            target = msg
            
        if delete_after:
            # Tell the bot to delete this message after X seconds
            asyncio.create_task(delayed_delete(target, delete_after))
    except Exception as e:
        log.error(f"UI Respond error: {e}")

# Simple math to turn seconds (like 90) into a string (like 1:30)
def format_duration(seconds: int):
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

# Safety helper to delete a message without the bot crashing if the message is already gone
async def safe_delete_message(message: discord.Message | None):
    if not message:
        return
    try:
        await message.delete()
    except:
        # If it fails, it probably just doesn't exist anymore, which is fine!
        pass

# Safety helper to find a message in a channel by its ID
async def safe_fetch_message(channel, message_id: int | None):
    if not message_id:
        return None
    try:
        return await channel.fetch_message(message_id)
    except:
        # If we can't find it, we just return nothing (None)
        return None


