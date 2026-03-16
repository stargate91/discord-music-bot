import discord
from discord.ui import Modal, TextInput, ActionRow, Container, Section, TextDisplay, Separator
from ui_translate import t
from ui_icons import Icons
from ui_base import handle_ui_error, PaginatedView
from ui_utils import safe_delete_message, safe_fetch_message, format_duration
from radio_actions import RadioAction, RadioState
from logger import log
from ui_theme import Theme

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
            placeholder="https://youtube.com/watch?v=... or https://soundcloud.com/...",
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
            placeholder="Artist, Song Title...",
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
                results.extend(provider_results)
        
        if not results:
            log.info(f"[SEARCH] No results found for: {query}")
            await interaction.followup.send(t("empty"), ephemeral=True)
            return

        log.info(f"[SEARCH] Found {len(results)} results for: {query}")
        view = SearchResultsView(self.radio, results)
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
        self.radio.dispatch(RadioAction.ADD_EXT_LINK, self.result['path'], user=interaction.user)
        await interaction.followup.send(t("weblink_added"), ephemeral=True)

class SearchResultsView(PaginatedView):
    def __init__(self, radio, results, page=0):
        super().__init__(radio, results, items_per_page=5, page=page)
        self.results = results
        
        container = Container(accent_color=Theme.PRIMARY)
        container.add_item(TextDisplay(f"### {Icons.SEARCH} {t('search_results_title')}"))
        container.add_item(Separator())
        
        def truncate(text, max_len):
            return (text[:max_len-3] + '...') if len(text) > max_len else text

        items = self.get_page_items()
        for i, res in enumerate(items, self.current_page * self.items_per_page + 1):
            t_artist = truncate(res.get('artist') or t('unknown'), radio.config.max_uploader_len)
            t_title = truncate(res.get('title') or t('unknown'), radio.config.max_title_len)
            
            info = f"**{i}. {t_artist} - {t_title}** (`{format_duration(res['duration'])}`)"
            container.add_item(TextDisplay(info))
            
            row = ActionRow()
            row.add_item(SearchResultAddButton(radio, res))
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
        
        close = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.secondary)
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
        new_view = SearchResultsView(self.radio, self.results, page=self.current_page)
        await interaction.edit_original_response(view=new_view)

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
        # 4 tracks per page: Each track uses 1 Text + 1 Row (with 3 buttons) = 4 items? 
        # Actually safer to stick to 4 to avoid the 40 limit which seems to count nested items too.
        super().__init__(radio, radio.queue, items_per_page=4, page=page)
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
                raw_name = song.get('uploader') or song.get('artist') or t('unknown')
                raw_title = song.get('title', t('unknown'))
                
                t_name = truncate(raw_name, radio.config.max_uploader_len)
                t_title = truncate(raw_title, radio.config.max_title_len)
                
                song_info = f"**{i}.** {t_name} - {t_title}"
                
                # Add text info first
                container.add_item(TextDisplay(song_info))
                
                # Then add control buttons in a single row
                row = ActionRow()
                is_first = (i == 1)
                is_last = (i == len(radio.queue))
                row.add_item(MoveUpButton(radio, song, is_first=is_first))
                row.add_item(MoveDownButton(radio, song, is_last=is_last))
                row.add_item(RemoveFromQueueButton(radio, song))
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
        
        close = discord.ui.Button(emoji=Icons.CLOSE, style=discord.ButtonStyle.secondary)
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
