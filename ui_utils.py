import discord
import asyncio
from ui_icons import Icons
from ui_translate import t
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

def get_feedback(key: str, **kwargs) -> str:
    """
    Returns a translated string prefixed with the appropriate emoji.
    """
    icons_map = {
        # --- Errors & Warnings ---
        "not_in_same_voice": Icons.WARNING,      # Csatlakozz ugyanahhoz a hangcsatornához...
        "no_permission": Icons.WARNING,          # Nincs jogod ehhez a csatornához...
        "admin_only": Icons.WARNING,             # Ehhez adminnak vagy rendszergazdának kell lenned.
        "error_generic": Icons.WARNING,          # Hiba történt a kérés feldolgozása közben.
        "cannot_pause_stopped": Icons.WARNING,   # Álló helyzetben nem tudod szüneteltetni.
        "cannot_seek_stopped": Icons.WARNING,    # Álló helyzetben nem tudsz tekerni.
        "vol_range_error": Icons.WARNING,        # 0 és 100 között adj meg valamit.
        "no_current_track": Icons.WARNING,       # Nincs mihez ugrani.
        "no_next_track": Icons.WARNING,          # Nincs több szám a várólistában.
        "no_prev_track": Icons.WARNING,          # Nincs korábbi szám az előzményekben.
        "format_error": Icons.WARNING,           # Használd a pp:mp formátumot!
        "too_long": Icons.WARNING,               # Ilyen hosszú nincs is ez a szám.
        "cooldown_error": Icons.WARNING,         # Várj egy kicsit, pihen a rendszer...
        "weblink_error": Icons.WARNING,          # Érvénytelen vagy nem támogatott link!
        "nothing_playing": Icons.WARNING,        # Most épp semmi nem szól.
        "invalid_number": Icons.WARNING,         # Ez nem egy szám!
        "empty": Icons.WARNING,                  # Üres...
        
        # --- Headers / Titles ---
        "help_title": Icons.HELP,                 # Bot Segítség & Parancsok
        "search_results_title": Icons.SEARCH,     # Keresési Találatok
        "library_label": Icons.FOLDER_HEART,      # Saját Gyűjtemény
        "history_label": Icons.HISTORY,           # Előzmények
        "queue_label": Icons.QUEUE,               # Várólista
        
        # --- Processing / Waiting ---
        "search_processing": Icons.SEARCH,       # Keresés a YouTube-on...
        "weblink_processing": Icons.GLOBE,       # Link feldolgozása, kis türelmet...
        "syncing": Icons.SYNC,                   # Csatlakozás...
        "severing": Icons.CLOSE,                 # Lecsatlakozás...
        "resuming": Icons.PLAY,                  # Folytatás...
        "forwarding": Icons.NEXT,                # Következő szám...
        "jumping": Icons.SEEK,                   # Ugrás ide: [időpont]
        "restarting": Icons.SYNC,                # Bot újraindítása...
        
        # --- Success / Confirmation ---
        "weblink_added": Icons.QUEUE,            # Link hozzáadva a várólistához!
        "vol_set": Icons.VOLUME,                 # Hangerő beállítva: [százalék]
        "added_to_fav": Icons.HEART_PLUS,        # Hozzáadva a kedvencekhez!
        "removed_from_fav": Icons.HEART_MINUS,   # Eltávolítva a kedvencekből!
        "added_all_to_queue": Icons.QUEUE,       # Az összes dalt hozzáadtam a várólistához!
        "cleared_favorites": Icons.SWEEP,        # A teljes gyűjteményt töröltem!
        "cleared_history": Icons.SWEEP,          # Lejátszási előzmények törölve!
        "queue_shuffled": Icons.SWEEP,           # Várólista megkeverve!
        "shuffle_feedback": Icons.SWEEP,         # Várólista megkeverve!
        "resuming_feedback": Icons.PLAY,         # Zene folytatása...
        "pausing": Icons.PAUSE,                  # Szünet...
        "stopping": Icons.STOP,                  # Leállítás...
        "loop_enabled": Icons.REPEAT,            # Végtelenített lejátszás bekapcsolva.
        "loop_disabled": Icons.CLOSE,            # Végtelenített lejátszás kikapcsolva.
        "loop_queue_enabled": Icons.REPEAT,      # Várólista végtelenítés bekapcsolva.
        "loop_queue_disabled": Icons.CLOSE,      # Várólista végtelenítés kikapcsolva.
        "loop_toggle": Icons.REPEAT,             # Végtelenített lejátszás állapota megváltozott.
        "loop_queue_toggle": Icons.REPEAT,       # Várólista végtelenítés állapota megváltozott.
        "back_label": Icons.BACK,                # Vissza...
    }
    
    emoji = icons_map.get(key, "")
    text = t(key, **kwargs)
    
    if not text:
        log.warning(f"[UI] Missing translation key for feedback: {key}")
        return f"{emoji} {key}".strip()
        
    return f"{emoji} {text}".strip()

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


