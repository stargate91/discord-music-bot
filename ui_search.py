import discord
from discord.ui import Modal, TextInput, ActionRow, Container, Section, TextDisplay, Separator
from ui_translate import t
from ui_icons import Icons
from ui_base import handle_ui_error, PaginatedView
from ui_utils import safe_delete_message, safe_fetch_message, format_duration
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
        await interaction.followup.send(t("weblink_added"), ephemeral=True)

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
        msg = await interaction.followup.send(t("search_processing"), ephemeral=True)
        log.info(f"[SEARCH] User {interaction.user.name} searched for: {query}")
        
        results = []
        for provider in self.radio.providers:
            # We only search with YTDLP for now as per request
            if hasattr(provider, 'search'):
                provider_results = await provider.search(query, limit=20)
                # Convert dict results to Song objects
                results.extend([Song.from_dict(res) for res in provider_results])
        
        if not results:
            log.info(f"[SEARCH] No results found for: {query}")
            await interaction.followup.send(t("empty"), ephemeral=True)
            return

        log.info(f"[SEARCH] Found {len(results)} results for: {query}")
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
        await interaction.followup.send(t("weblink_added"), ephemeral=True)

class FavoriteListButton(discord.ui.Button):
    def __init__(self, radio, song: Song):
        # We check the status for the initial state if possible
        # but since it's a list, it's better to stay neutral or check on init
        super().__init__(emoji=Icons.HEART_PLUS, style=discord.ButtonStyle.secondary)
        self.radio = radio
        self.song = song

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        # Perform the toggle in the manager
        added = self.radio.fav_manager.toggle_favorite(interaction.user.id, self.song)
        
        # Update button emoji for immediate visual feedback
        self.emoji = Icons.HEART_MINUS if added else Icons.HEART_PLUS
        
        # Defer so we can edit the original message
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
            
        # Refresh the entire list view so icons are updated everywhere (if parent is PaginatedView)
        try:
            await interaction.edit_original_response(view=self.view)
        except Exception:
            # Fallback if refresh fails
            pass
            
        icon = Icons.HEART_PLUS if added else Icons.HEART_MINUS
        msg = t("added_to_fav") if added else t("removed_from_fav")
        await interaction.followup.send(f"{icon} {msg}", ephemeral=True)

class SearchResultsView(PaginatedView):
    def __init__(self, radio, results, query=None, user=None, page=0):
        # Safety conversion for legacy dict results
        results = [Song.from_dict(r) if isinstance(r, dict) else r for r in results]
        super().__init__(radio, results, items_per_page=8, page=page)
        self.results = results
        self.query = query
        self.user = user
        
        container = Container(accent_color=Theme.PRIMARY)
        
        # Build header with query and user
        header_text = f"### {Icons.SEARCH} {t('search_results_title')}"
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
            t_title = truncate(res.title or t('unknown'), radio.config.list_max_title_len)
            
            info = f"**{i}. {t_title}** ({format_duration(res.duration)})"
            container.add_item(TextDisplay(info))
            
            row = ActionRow()
            row.add_item(SearchResultAddButton(radio, res))
            row.add_item(FavoriteListButton(radio, res))
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
        await interaction.followup.send(f"{Icons.REMOVE} {t('removed_from_fav')}", ephemeral=True)

class FavoritesView(PaginatedView):
    def __init__(self, radio, user_id, page=0):
        favs = radio.fav_manager.get_favorites(user_id)
        super().__init__(radio, favs, items_per_page=5, page=page)
        self.user_id = user_id
        
        container = Container(accent_color=Theme.PRIMARY)
        container.add_item(TextDisplay(f"### {Icons.FOLDER_HEART} {t('library_label')}"))
        container.add_item(Separator())
        
        if not favs:
            container.add_item(TextDisplay(f"*{t('empty')}*"))
        else:
            def truncate(text, max_len):
                return (text[:max_len-3] + '...') if len(text) > max_len else text

            items = self.get_page_items()
            for i, song in enumerate(items, self.current_page * self.items_per_page + 1):
                t_title = truncate(song.title or t('unknown'), radio.config.list_max_title_len)
                
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
        await interaction.response.defer()
        for song in self.songs:
            # Create a clean copy without internal state for the queue
            q_song = Song.from_dict(song.to_dict())
            q_song.requested_by = interaction.user.name
            self.radio.queue.append(q_song)
            
        await interaction.followup.send(f"{Icons.QUEUE} {t('added_all_to_queue')}", ephemeral=True)

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
        self.radio.fav_manager.clear_favorites(self.user_id)
        
        await interaction.response.defer()
        if hasattr(self.view, 'refresh_view'):
            self.view.current_page = 0
            self.view.data_list = []
            await self.view.refresh_view(interaction)
            
        await interaction.followup.send(f"{Icons.SWEEP} {t('cleared_favorites')}", ephemeral=True)

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
        super().__init__(radio, history, items_per_page=8, page=page)
        self.radio = radio
        self.user = user
        
        container = Container(accent_color=Theme.PRIMARY)
        container.add_item(TextDisplay(f"### {Icons.HISTORY} {t('history_label')}"))
        container.add_item(Separator())
        
        if not history:
            container.add_item(TextDisplay(f"*{t('no_prev_track')}*"))
        else:
            def truncate(text, max_len):
                return (text[:max_len-3] + '...') if len(text) > max_len else text

            items = self.get_page_items()
            for i, song in enumerate(items, self.current_page * self.items_per_page + 1):
                t_title = truncate(song.title or t('unknown'), radio.config.list_max_title_len)
                t_user = song.requested_by or t('unknown')
                t_played = song.played_at or ""
                
                info = f"**{i}. {t_title}** ({format_duration(song.duration)})\n*{t_played} - {t_user}*"
                container.add_item(TextDisplay(info))
                
                row = ActionRow()
                row.add_item(SearchResultAddButton(radio, song))
                row.add_item(FavoriteListButton(radio, song))
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
            await interaction.response.send_message(t("admin_only"), ephemeral=True)
            return

        # Simple confirmation check would be nice, but for now direct clear
        self.radio.history_manager.clear()
        
        await interaction.response.defer()
        if hasattr(self.view, 'refresh_view'):
            # Reset to page 0 since history is gone
            self.view.current_page = 0
            # History will be empty now
            self.view.data_list = []
            await self.view.refresh_view(interaction)
        
        await interaction.followup.send(f"{Icons.SWEEP} History cleared!", ephemeral=True)

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
        view = FullQueueView(self.radio, page=0)
        await interaction.response.send_message(view=view, ephemeral=True)

class RemoveFromQueueButton(discord.ui.Button):
    def __init__(self, radio, song):
        super().__init__(emoji=Icons.REMOVE, style=discord.ButtonStyle.secondary)
        self.radio = radio
        self.song = song

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.song in self.radio.queue:
            self.radio.queue.remove(self.song)
        await self.view.refresh_view(interaction)

class ClearQueueButton(discord.ui.Button):
    def __init__(self, radio):
        super().__init__(label=t("clear_queue_label"), emoji=Icons.SWEEP, style=discord.ButtonStyle.secondary)
        self.radio = radio

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.radio.queue = []
        await self.view.refresh_view(interaction)

class MoveUpButton(discord.ui.Button):
    def __init__(self, radio, song, is_first=False):
        super().__init__(emoji=Icons.MOVE_UP, style=discord.ButtonStyle.secondary, disabled=is_first)
        self.radio = radio
        self.song = song

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            idx = self.radio.queue.index(self.song)
            if idx > 0:
                self.radio.queue[idx], self.radio.queue[idx-1] = self.radio.queue[idx-1], self.radio.queue[idx]
        except ValueError: pass
        await self.view.refresh_view(interaction)

class MoveDownButton(discord.ui.Button):
    def __init__(self, radio, song, is_last=False):
        super().__init__(emoji=Icons.MOVE_DOWN, style=discord.ButtonStyle.secondary, disabled=is_last)
        self.radio = radio
        self.song = song

    @handle_ui_error
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            idx = self.radio.queue.index(self.song)
            if idx < len(self.radio.queue) - 1:
                self.radio.queue[idx], self.radio.queue[idx+1] = self.radio.queue[idx+1], self.radio.queue[idx]
        except ValueError: pass
        await self.view.refresh_view(interaction)

class FullQueueView(PaginatedView):
    def __init__(self, radio, page=0):
        # Force all items to be Song objects if they are dicts
        queue = [Song.from_dict(r) if isinstance(r, dict) else r for r in radio.queue]
        # 6 tracks per page: Each track uses 1 Text + 1 Row (with 4 buttons)
        super().__init__(radio, queue, items_per_page=6, page=page)
        container = Container(accent_color=Theme.PRIMARY)
        container.add_item(TextDisplay(f"### {Icons.QUEUE} {t('queue_label')}"))
        container.add_item(Separator())
        
        if not self.data_list:
            container.add_item(TextDisplay(f"*{t('empty')}*"))
        else:
            def truncate(text, max_len):
                return (text[:max_len-3] + '...') if len(text) > max_len else text

            items = self.get_page_items()
            for i, song in enumerate(items, self.current_page * self.items_per_page + 1):
                raw_name = song.uploader or t('unknown')
                raw_title = song.title or t('unknown')
                
                t_name = truncate(raw_name, radio.config.max_uploader_len)
                t_title = truncate(raw_title, radio.config.list_max_title_len)
                
                song_info = f"**{i}. {t_title}**\n{t_name} ({format_duration(song.duration)})"
                
                # Add text info first
                container.add_item(TextDisplay(song_info))
                
                # Then add control buttons in a single row
                row = ActionRow()
                is_first = (i == 1)
                is_last = (i == len(radio.queue))
                row.add_item(MoveUpButton(radio, song, is_first=is_first))
                row.add_item(MoveDownButton(radio, song, is_last=is_last))
                row.add_item(RemoveFromQueueButton(radio, song))
                row.add_item(FavoriteListButton(radio, song))
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
        new_view = FullQueueView(self.radio, page=self.current_page)
        await interaction.edit_original_response(view=new_view)
