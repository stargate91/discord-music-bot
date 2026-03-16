import discord
import traceback
from discord.ui import LayoutView
from ui_icons import Icons
from ui_translate import t
from logger import log

def handle_ui_error(func):
    """Decorator to handle errors in UI callbacks gracefully."""
    async def wrapper(*args, **kwargs):
        interaction = next((arg for arg in args if isinstance(arg, discord.Interaction)), None)
        try:
            return await func(*args, **kwargs)
        except (discord.errors.NotFound, discord.errors.HTTPException) as e:
            # Handle known noise errors
            code = getattr(e, 'code', 0)
            if code in [10062, 40060]: 
                return # Silent ignore for these
            
            log.error(f"UI Error in {func.__name__}: {e}")
            await _send_error_msg(interaction)
        except Exception as e:
            log.error(f"UI Error in {func.__name__}: {e}")
            traceback.print_exc()
            await _send_error_msg(interaction)
    return wrapper

async def _send_error_msg(interaction):
    if not interaction: return
    error_msg = t('error_generic') or "An error occurred."
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"{Icons.WARNING} {error_msg}", ephemeral=True)
        else:
            await interaction.followup.send(f"{Icons.WARNING} {error_msg}", ephemeral=True)
    except:
        pass # Final line of defense

class BaseView(LayoutView):
    """Base class for all Radio Bot views with shared logic."""

    def __init__(self, radio, timeout=None):
        super().__init__(timeout=timeout)
        self.radio = radio
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        log.error(f"View Error: {error} in {item}")
        traceback.print_exc()
        error_msg = t('error_generic') or "An error occurred."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"{Icons.WARNING} {error_msg}", ephemeral=True)
            else:
                await interaction.followup.send(f"{Icons.WARNING} {error_msg}", ephemeral=True)
        except discord.errors.NotFound:
            log.warning(f"Could not send view error message (interaction expired): {error}")
        except Exception as e:
            log.error(f"Error in View.on_error: {e}")

class PaginatedView(BaseView):
    """Base class for views requiring pagination."""

    def __init__(self, radio, data_list, items_per_page=5, timeout=None, page=0):
        super().__init__(radio, timeout=timeout)
        self.data_list = data_list
        self.items_per_page = items_per_page
        self.current_page = page
        self.total_pages = max(1, (len(data_list) + items_per_page - 1) // items_per_page)

    def get_page_items(self):
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        return self.data_list[start:end]

    def update_pagination_buttons(self, prev_button, next_button):
        """Helper to update state of Prev/Next buttons."""
        if prev_button:
            prev_button.disabled = (self.current_page == 0)
        if next_button:
            next_button.disabled = (self.current_page >= self.total_pages - 1)

    @property
    def pagination_info(self):
        return f"{t('page')} {self.current_page + 1} / {self.total_pages} ({len(self.data_list)} {t('total')})"
