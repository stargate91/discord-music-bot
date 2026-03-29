import discord
from typing import Optional
import asyncio
from discord.ui import Modal, TextInput, ActionRow, Container, Section, TextDisplay, Separator
from ui_translate import t
from ui_icons import Icons
from ui_base import handle_ui_error, PaginatedView
from ui_utils import safe_delete_message, safe_fetch_message, format_duration, respond, get_feedback
from radio_actions import RadioAction, RadioState
from logger import log
from ui_theme import Theme
from core.models import Song

class WebLinkButton(discord.ui.Button):
    def __init__(self, radio, custom_id="weblink_button"):
        super().__init__(
            label=None if radio.is_compact else t('weblink_label'),
            emoji=Icons.GLOBE,
            style=discord.ButtonStyle.secondary,
            custom_id=custom_id
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        modal = WebLinkModal(self.radio)
        await interaction.response.send_modal(modal)

class WebLinkModal(Modal):
    def __init__(self, radio):
        super().__init__(title=t("weblink_modal_title"))
        self.radio = radio
        self.url_input = TextInput(
            label=t("weblink_input_label"),
            placeholder=t('weblink_placeholder'),
            style=discord.TextStyle.short,
            required=True,
            min_length=5
        )
        self.add_item(self.url_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        url = self.url_input.value.strip()
        if not url: return
        
        self.radio.dispatch(RadioAction.ADD_EXT_LINK, url, user=interaction.user)
        await respond(interaction, get_feedback("weblink_added"), delete_after=self.radio.config.notification_timeout)

class SearchButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=None if radio.is_compact else t('search_label'),
            emoji=Icons.SEARCH,
            style=discord.ButtonStyle.secondary,
            custom_id="search_modal_open"
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        modal = SearchModal(self.radio)
        await interaction.response.send_modal(modal)

class SearchModal(Modal):
    def __init__(self, radio):
        super().__init__(title=t("search_modal_title"))
        self.radio = radio
        self.query_input = TextInput(
            label=t("search_input_label"),
            placeholder=t('search_placeholder'),
            style=discord.TextStyle.short,
            required=True,
            min_length=2
        )
        self.add_item(self.query_input)

    @handle_ui_error
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        query = self.query_input.value.strip()
        
        # Searching...
        msg = await interaction.followup.send(get_feedback("search_processing"), ephemeral=True)
        log.info(f"[SEARCH] User {interaction.user.name} searched for: {query}")
        
        results = []
        for provider in self.radio.providers:
            # We only search with YTDLP for now as per request
            if hasattr(provider, 'search'):
                provider_results = await provider.search(query, limit=self.radio.config.search_limit)
                # Convert dict results to Song objects
                results.extend([Song.from_dict(res) for res in provider_results])
        
        if not results:
            log.info(f"[SEARCH] No results found for: {query}")
            await interaction.followup.send(get_feedback("empty"), ephemeral=True)
            return

        log.info(f"[SEARCH] Found {len(results)} results for: {query}")
        
        # Best Practice: Auto-populate the cache with search results
        for song in results:
            self.radio.db.set_cache(
                url=song.path,
                title=song.title,
                uploader=song.uploader or "Unknown",
                duration=song.duration,
                thumbnail_url=song.thumbnail_url or ""
            )
            
        view = SearchResultsView(self.radio, results, query=query, user=interaction.user)
        await interaction.followup.send(view=view, ephemeral=True)
        await safe_delete_message(msg)

class SearchResultAddButton(discord.ui.Button):
    def __init__(self, radio, result):
        super().__init__(emoji=Icons.ADD, style=discord.ButtonStyle.secondary)
        self.radio = radio
        self.result = result

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.radio.dispatch(RadioAction.ADD_EXT_LINK, self.result.path, user=interaction.user)
        await respond(interaction, get_feedback("weblink_added"), delete_after=self.radio.config.notification_timeout)

class FavoriteListButton(discord.ui.Button):
    def __init__(self, radio, song: Song, user_id: Optional[int] = None):
        as_fav = False
        if user_id:
            as_fav = radio.fav_manager.is_favorite(user_id, song)
            
        emoji = Icons.HEART_MINUS if as_fav else Icons.HEART_PLUS
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary)
        self.radio = radio
        self.song = song
    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        # Determine movement direction BEFORE dispatching the action 
        # to ensure correct feedback regardless of how fast the engine is.
        is_fav_now = self.radio.fav_manager.is_favorite(interaction.user.id, self.song)
        will_be_added = not is_fav_now

        # Dispatch the toggle action
        self.radio.dispatch(RadioAction.TOGGLE_FAVORITE, (interaction.user.id, self.song), user=interaction.user)
        
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # Refresh the view state if possible
        try:
            if hasattr(self.view, 'refresh_view'):
                await self.view.refresh_view(interaction)
            else:
                await interaction.edit_original_response(view=self.view)
        except Exception as e:
            log.debug(f"[UI] Favorite refresh failed (non-critical): {e}")

        # Correct feedback based on state before dispatch
        key = "added_to_fav" if will_be_added else "removed_from_fav"
        
        await respond(interaction, get_feedback(key), delete_after=self.radio.config.notification_timeout)

class SearchResultsView(PaginatedView):
    def __init__(self, radio, results, query=None, user=None, page=0):
        # Safety conversion for legacy dict results
        results = [Song.from_dict(r) if isinstance(r, dict) else r for r in results]
        super().__init__(radio, results, items_per_page=radio.config.search_items_per_page, page=page)
        self.results = results
        self.query = query
        self.user = user
        
        container = Container(accent_color=Theme.PRIMARY)
        
        # Build header with query and user
        header_text = f"### {get_feedback('search_results_title')}"
        if query:
            header_text += f" - *\"{query}\"*"
        if user:
            header_text += f" ({user.name})"
            
        container.add_item(TextDisplay(header_text))
        container.add_item(Separator())
        
        def truncate(text, max_len):
            return (text[:max_len-3] + '...') if len(text) > max_len else text

        items = self.get_page_items()
        for i, res in enumerate(items, self.current_page * self.items_per_page + 1):
            t_title = truncate(res.title or get_feedback('unknown'), radio.config.list_max_title_len)
            
            info = f"**{i}. {t_title}** ({format_duration(res.duration)})"
            container.add_item(TextDisplay(info))
            
            row = ActionRow()
            row.add_item(SearchResultAddButton(radio, res))
            row.add_item(FavoriteListButton(radio, res, user_id=self.user.id if self.user else None))
            container.add_item(row)
            
        container.add_item(Separator())
        container.add_item(TextDisplay(f"{t('results_label')}: {len(results)} | {self.pagination_info}"))
        
        nav = ActionRow()
        prev = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary)
        next = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary)
        self.update_pagination_buttons(prev, next)
        
        @handle_ui_error
        async def prev_cb(interaction):
            await interaction.response.defer()
            self.current_page -= 1
            await self.refresh_view(interaction)
        prev.callback = prev_cb

        @handle_ui_error
        async def next_cb(interaction):
            await interaction.response.defer()
            self.current_page += 1
            await self.refresh_view(interaction)
        next.callback = next_cb
        
        close = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.danger)
        @handle_ui_error
        async def close_cb(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()
        close.callback = close_cb

        nav.add_item(prev)
        nav.add_item(next)
        nav.add_item(close)
        container.add_item(nav)
        
        self.add_item(container)

    async def refresh_view(self, interaction):
        new_view = SearchResultsView(
            self.radio, 
            self.results, 
            query=self.query, 
            user=self.user, 
            page=self.current_page
        )
        await interaction.edit_original_response(view=new_view)

class LibraryButton(discord.ui.Button):
    def __init__(self, radio, custom_id="library_button"):
        super().__init__(
            label=None if radio.is_compact else t('library_label'),
            emoji=Icons.FOLDER_HEART,
            style=discord.ButtonStyle.secondary,
            custom_id=custom_id
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        view = FavoritesView(self.radio, interaction.user.id)
        await interaction.response.send_message(view=view, ephemeral=True)

class FavoriteRemoveButton(discord.ui.Button):
    def __init__(self, radio, song: Song):
        super().__init__(emoji=Icons.REMOVE, style=discord.ButtonStyle.secondary)
        self.radio = radio
        self.song = song

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        # We know it's already a favorite since it's in this list, so toggle will remove it
        self.radio.fav_manager.toggle_favorite(interaction.user.id, self.song)
        
        # Defer the interaction so we can update the list
        await interaction.response.defer(ephemeral=True)
        
        # Refresh the parent FavoritesView
        if hasattr(self.view, 'refresh_view'):
            await self.view.refresh_view(interaction)
            
        # Optional: send a followup confirmation
        await respond(interaction, get_feedback('removed_from_fav'), delete_after=self.radio.config.notification_timeout)

class FavoritesView(PaginatedView):
    def __init__(self, radio, user_id, page=0):
        favs = radio.fav_manager.get_favorites(user_id)
        super().__init__(radio, favs, items_per_page=radio.config.search_items_per_page, page=page)
        self.user_id = user_id
        
        container = Container(accent_color=Theme.PRIMARY)
        container.add_item(TextDisplay(f"### {get_feedback('library_label')}"))
        container.add_item(Separator())
        
        if not favs:
            container.add_item(TextDisplay(f"*{get_feedback('empty')}*"))
        else:
            def truncate(text, max_len):
                return (text[:max_len-3] + '...') if len(text) > max_len else text

            items = self.get_page_items()
            for i, song in enumerate(items, self.current_page * self.items_per_page + 1):
                t_title = truncate(song.title or get_feedback('unknown'), radio.config.list_max_title_len)
                
                info = f"**{i}. {t_title}** ({format_duration(song.duration)})"
                container.add_item(TextDisplay(info))
                
                row = ActionRow()
                row.add_item(SearchResultAddButton(radio, song))
                row.add_item(FavoriteRemoveButton(radio, song))
                container.add_item(row)
                
        container.add_item(Separator())
        container.add_item(TextDisplay(self.pagination_info))
        
        nav = ActionRow()
        prev = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary)
        next = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary)
        self.update_pagination_buttons(prev, next)
        
        @handle_ui_error
        async def prev_cb(interaction):
            await interaction.response.defer()
            self.current_page -= 1
            await self.refresh_view(interaction)
        prev.callback = prev_cb

        @handle_ui_error
        async def next_cb(interaction):
            await interaction.response.defer()
            self.current_page += 1
            await self.refresh_view(interaction)
        next.callback = next_cb
        
        close = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.danger)
        @handle_ui_error
        async def close_cb(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()
        close.callback = close_cb

        nav.add_item(prev)
        nav.add_item(next)
        
        if favs:
            nav.add_item(AddAllFavoritesButton(radio, favs))
            nav.add_item(ClearFavoritesButton(radio, self.user_id))

        nav.add_item(close)
        container.add_item(nav)
        
        self.add_item(container)

    async def refresh_view(self, interaction):
        new_view = FavoritesView(self.radio, self.user_id, page=self.current_page)
        await interaction.edit_original_response(view=new_view)

class AddAllFavoritesButton(discord.ui.Button):
    def __init__(self, radio, songs):
        super().__init__(
            label=t("add_all_to_queue"),
            emoji=Icons.QUEUE,
            style=discord.ButtonStyle.secondary
        )
        self.radio = radio
        self.songs = songs

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        # Check permissions
        if not self.radio.can_interact(interaction.user):
            await interaction.response.send_message(get_feedback("not_in_same_voice"), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        log.info(f"[UI] AddAllFavoritesButton clicked by {interaction.user.name}. Total songs in list: {len(self.songs)}")
        
        # Create clean copies without internal state for the queue
        q_songs = []
        for song in self.songs:
            q_song = Song.from_dict(song.to_dict())
            q_song.requested_by = interaction.user.display_name
            q_songs.append(q_song)
        
        # Ensure bot is in voice if we want it to start playing immediately
        if self.radio.voice_channel_id is None:
            if not interaction.user.voice:
                await interaction.followup.send(get_feedback("no_permission"), ephemeral=True)
                return
            self.radio.dispatch(RadioAction.JOIN, interaction.user.voice.channel.id, user=interaction.user)

        # Dispatch as action to wake up the engine if idle
        self.radio.dispatch(RadioAction.ADD_SONGS, q_songs, user=interaction.user)
            
        await respond(interaction, get_feedback('added_all_to_queue'), delete_after=self.radio.config.notification_timeout)

class ClearFavoritesButton(discord.ui.Button):
    def __init__(self, radio, user_id):
        super().__init__(
            label=t("clear_favorites"),
            emoji=Icons.SWEEP,
            style=discord.ButtonStyle.secondary
        )
        self.radio = radio
        self.user_id = user_id

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        self.radio.dispatch(RadioAction.CLEAR_FAVORITES, self.user_id, user=interaction.user)
        
        await interaction.response.defer()
        if hasattr(self.view, 'refresh_view'):
            self.view.current_page = 0
            self.view.data_list = []
            await self.view.refresh_view(interaction)
            
        await respond(interaction, get_feedback('cleared_favorites'), delete_after=self.radio.config.notification_timeout)

class HistoryButton(discord.ui.Button):
    def __init__(self, radio, custom_id="history_button"):
        super().__init__(
            label=None if radio.is_compact else t('history_label'),
            emoji=Icons.HISTORY,
            style=discord.ButtonStyle.secondary,
            custom_id=custom_id
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        view = HistoryView(self.radio, user=interaction.user)
        await interaction.response.send_message(view=view, ephemeral=True)

class HistoryView(PaginatedView):
    def __init__(self, radio, page=0, user=None):
        # The history list from the radio
        history = [Song.from_dict(r) if isinstance(r, dict) else r for r in radio.history]
        super().__init__(radio, history, items_per_page=radio.config.search_items_per_page, page=page)
        self.radio = radio
        self.user = user
        
        container = Container(accent_color=Theme.PRIMARY)
        container.add_item(TextDisplay(f"### {get_feedback('history_label')}"))
        container.add_item(Separator())
        
        if not history:
            container.add_item(TextDisplay(f"*{get_feedback('no_prev_track')}*"))
        else:
            def truncate(text, max_len):
                return (text[:max_len-3] + '...') if len(text) > max_len else text

            items = self.get_page_items()
            for i, song in enumerate(items, self.current_page * self.items_per_page + 1):
                t_title = truncate(song.title or get_feedback('unknown'), radio.config.list_max_title_len)
                t_user = song.requested_by or get_feedback('unknown')
                t_played = song.played_at or ""
                
                info = f"**{i}. {t_title}** ({format_duration(song.duration)})\n*{t_played} - {t_user}*"
                container.add_item(TextDisplay(info))
                
                row = ActionRow()
                row.add_item(SearchResultAddButton(radio, song))
                row.add_item(FavoriteListButton(radio, song, user_id=self.user.id if self.user else None))
                container.add_item(row)
                
        container.add_item(Separator())
        container.add_item(TextDisplay(self.pagination_info))
        
        nav = ActionRow()
        prev = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary)
        next = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary)
        self.update_pagination_buttons(prev, next)
        
        @handle_ui_error
        async def prev_cb(interaction):
            await interaction.response.defer()
            self.current_page -= 1
            await self.refresh_view(interaction)
        prev.callback = prev_cb

        @handle_ui_error
        async def next_cb(interaction):
            await interaction.response.defer()
            self.current_page += 1
            await self.refresh_view(interaction)
        next.callback = next_cb
        
        close = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.danger)
        @handle_ui_error
        async def close_cb(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()
        close.callback = close_cb

        nav.add_item(prev)
        nav.add_item(next)
        
        # Admin only: Clear History
        if user and radio.is_admin(user):
            nav.add_item(ClearHistoryButton(radio))

        nav.add_item(close)
        container.add_item(nav)
        
        self.add_item(container)

    async def refresh_view(self, interaction):
        new_view = HistoryView(self.radio, page=self.current_page, user=self.user)
        await interaction.edit_original_response(view=new_view)

class ClearHistoryButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(
            label=t("clear_history_label"), 
            emoji=Icons.SWEEP, 
            style=discord.ButtonStyle.secondary
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        # Additional check in callback for safety
        if not self.radio.is_admin(interaction.user):
            await interaction.response.send_message(get_feedback("admin_only"), ephemeral=True)
            return

        self.radio.dispatch(RadioAction.CLEAR_HISTORY, user=interaction.user)
        
        await interaction.response.defer()
        if hasattr(self.view, 'refresh_view'):
            # Reset to page 0 since history is gone
            self.view.current_page = 0
            # History will be empty now
            self.view.data_list = []
            await self.view.refresh_view(interaction)
        
        await respond(interaction, get_feedback("cleared_history"), delete_after=self.radio.config.notification_timeout)

class QueueViewButton(discord.ui.Button):
    def __init__(self, radio):
        from radio_actions import RadioState
        is_idle_empty = (radio.status == RadioState.IDLE) and (not radio.queue)
        super().__init__(
            label=None if radio.is_compact else t('queue_label'), 
            emoji=Icons.QUEUE, 
            style=discord.ButtonStyle.secondary, 
            custom_id="full_queue_view",
            disabled=is_idle_empty
        )
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        view = FullQueueView(self.radio, page=0, user=interaction.user)
        await interaction.response.send_message(view=view, ephemeral=True)

class RemoveFromQueueButton(discord.ui.Button):
    def __init__(self, radio, song):
        super().__init__(emoji=Icons.REMOVE, style=discord.ButtonStyle.secondary)
        self.radio = radio
        self.song = song

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.radio.dispatch(RadioAction.REMOVE_FROM_QUEUE, self.song, user=interaction.user)
        
        # Immediate local update for better UX
        if self.song in self.radio.queue:
            self.radio.queue.remove(self.song)
            
        if hasattr(self.view, 'refresh_view'):
            await self.view.refresh_view(interaction)

class ClearQueueButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(label=t("clear_queue_label"), emoji=Icons.SWEEP, style=discord.ButtonStyle.secondary)
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.radio.dispatch(RadioAction.CLEAR_QUEUE, user=interaction.user)
        
        # Immediate local update
        self.radio.queue = []
        if hasattr(self.view, 'refresh_view'):
            self.view.current_page = 0
            await self.view.refresh_view(interaction)

class MoveUpButton(discord.ui.Button):
    def __init__(self, radio, song, is_first=False):
        super().__init__(emoji=Icons.MOVE_UP, style=discord.ButtonStyle.secondary, disabled=is_first)
        self.radio = radio
        self.song = song

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.radio.dispatch(RadioAction.MOVE_SONG, (self.song, -1), user=interaction.user)
        
        # Small delay to allow engine to process the swap before we refresh the view
        await asyncio.sleep(0.1)
        if hasattr(self.view, 'refresh_view'):
            await self.view.refresh_view(interaction)

class MoveDownButton(discord.ui.Button):
    def __init__(self, radio, song, is_last=False):
        super().__init__(emoji=Icons.MOVE_DOWN, style=discord.ButtonStyle.secondary, disabled=is_last)
        self.radio = radio
        self.song = song

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.radio.dispatch(RadioAction.MOVE_SONG, (self.song, 1), user=interaction.user)
        
        # Small delay to allow engine to process the swap before we refresh the view
        await asyncio.sleep(0.1)
        if hasattr(self.view, 'refresh_view'):
            await self.view.refresh_view(interaction)

class FullQueueView(PaginatedView):
    def __init__(self, radio, page=0, user: Optional[discord.Member | discord.User] = None):
        # Force all items to be Song objects if they are dicts
        queue = [Song.from_dict(r) if isinstance(r, dict) else r for r in radio.queue]
        # 6 tracks per page (configurable)
        super().__init__(radio, queue, items_per_page=radio.config.queue_items_per_page, page=page)
        self.user = user
        container = Container(accent_color=Theme.PRIMARY)
        container.add_item(TextDisplay(f"### {get_feedback('queue_label')}"))
        container.add_item(Separator())
        
        if not self.data_list:
            container.add_item(TextDisplay(f"*{get_feedback('empty')}*"))
        else:
            def truncate(text, max_len):
                return (text[:max_len-3] + '...') if len(text) > max_len else text

            items = self.get_page_items()
            for i, song in enumerate(items, self.current_page * self.items_per_page + 1):
                raw_title = song.title or get_feedback('unknown')
                t_title = truncate(raw_title, radio.config.list_max_title_len)
                
                song_info = f"**{i}. {t_title}** ({format_duration(song.duration)})"
                
                # Add text info first
                container.add_item(TextDisplay(song_info))
                
                # Then add control buttons in a single row
                row = ActionRow()
                is_first = (i == 1)
                is_last = (i == len(radio.queue))
                row.add_item(MoveUpButton(radio, song, is_first=is_first))
                row.add_item(MoveDownButton(radio, song, is_last=is_last))
                row.add_item(RemoveFromQueueButton(radio, song))
                row.add_item(FavoriteListButton(radio, song, user_id=self.user.id if self.user else None))
                container.add_item(row)
                
        container.add_item(TextDisplay(self.pagination_info))
        
        nav = ActionRow()
        prev = discord.ui.Button(emoji=Icons.PREV, style=discord.ButtonStyle.secondary)
        next = discord.ui.Button(emoji=Icons.NEXT, style=discord.ButtonStyle.secondary)
        self.update_pagination_buttons(prev, next)
        
        @handle_ui_error
        async def prev_cb(interaction):
            await interaction.response.defer()
            self.current_page -= 1
            await self.refresh_view(interaction)
        prev.callback = prev_cb

        @handle_ui_error
        async def next_cb(interaction):
            await interaction.response.defer()
            self.current_page += 1
            await self.refresh_view(interaction)
        next.callback = next_cb
        
        close = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.danger)
        @handle_ui_error
        async def close_cb(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()
            
        close.callback = close_cb
        
        nav.add_item(prev)
        nav.add_item(next)
        nav.add_item(ClearQueueButton(radio))
        nav.add_item(close)
        container.add_item(nav)
        self.add_item(container)

    async def refresh_view(self, interaction):
        new_view = FullQueueView(self.radio, page=self.current_page, user=self.user)
        await interaction.edit_original_response(view=new_view)
