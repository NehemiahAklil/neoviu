"""Widgets for the grid TUI: covers, tiles, responsive grids and paged browsers."""

import logging
from typing import Any, List, Optional

from textual import work
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.events import Click, Resize
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static
from textual.worker import get_current_worker

from ...libs.media_api.types import MediaItem, MediaSearchResult
from . import covers
from .catalog import Loader, MenuEntry
from .formatting import badge, display_title, meta_line, new_episodes

logger = logging.getLogger(__name__)


class Cover(Widget):
    """Cover art that shows a text placeholder until the image has loaded."""

    DEFAULT_CSS = """
    Cover {
        width: 1fr;
        height: 1fr;
        align: center middle;
        background: $boost;
    }
    Cover > .cover-fallback {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
    }
    Cover > .cover-image {
        width: auto;
        height: auto;
    }
    """

    def __init__(self, url: Optional[str], fallback: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._url = url
        self._fallback = fallback

    def compose(self):
        yield Static(self._fallback, classes="cover-fallback", markup=False)

    def on_mount(self) -> None:
        if self._url and covers.image_widget() is not None:
            self._load(self._url)

    def set_url(self, url: Optional[str]) -> None:
        if url != self._url:
            self._url = url
            if url and covers.image_widget() is not None:
                self._load(url)

    @work(thread=True, exclusive=True, group="cover")
    def _load(self, url: str) -> None:
        image = covers.load_cover(url)
        if image is None or get_current_worker().is_cancelled:
            return
        self.app.call_from_thread(self._show, image)

    async def _show(self, image: Any) -> None:
        widget_cls = covers.image_widget()
        if widget_cls is None or not self.is_attached:
            return
        await self.query(".cover-fallback, .cover-image").remove()
        await self.mount(widget_cls(image, classes="cover-image"))


class Tile(Widget, can_focus=True):
    """A focusable grid cell that is chosen with Enter or a click."""

    class Chosen(Message):
        def __init__(self, tile: "Tile") -> None:
            super().__init__()
            self.tile = tile

        @property
        def control(self) -> "Tile":
            return self.tile

    BINDINGS = [Binding("enter,space", "choose", "Open", show=False)]

    def action_choose(self) -> None:
        self.post_message(self.Chosen(self))

    def on_click(self, event: Click) -> None:
        event.stop()
        self.focus()
        self.post_message(self.Chosen(self))


class MenuTile(Tile):
    DEFAULT_CSS = """
    MenuTile {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        border: round $primary 40%;
        background: $surface;
    }
    MenuTile:hover {
        background: $boost;
    }
    MenuTile:focus {
        border: round $accent;
        background: $accent 15%;
    }
    MenuTile > .tile-icon {
        width: 1fr;
        height: 1;
        text-align: center;
        color: $accent;
        text-style: bold;
    }
    MenuTile > .tile-title {
        width: 1fr;
        height: 1;
        text-align: center;
        text-style: bold;
    }
    MenuTile > .tile-description {
        width: 1fr;
        height: 1;
        text-align: center;
        color: $text-muted;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    """

    def __init__(self, entry: MenuEntry, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.entry = entry
        self.tooltip = entry.description

    def compose(self):
        yield Static(self.entry.icon, classes="tile-icon", markup=False)
        yield Static(self.entry.title, classes="tile-title", markup=False)
        yield Static(self.entry.description, classes="tile-description", markup=False)


class MediaCard(Tile):
    DEFAULT_CSS = """
    MediaCard {
        width: 1fr;
        height: 1fr;
        border: round $panel;
        background: $surface;
    }
    MediaCard:hover {
        border: round $accent 60%;
    }
    MediaCard:focus {
        border: round $accent;
        background: $boost;
    }
    MediaCard > Cover {
        height: 1fr;
    }
    MediaCard > .card-title {
        height: 2;
        padding: 0 1;
        text-style: bold;
    }
    MediaCard > .card-meta {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    MediaCard > .card-badge {
        height: 1;
        padding: 0 1;
        color: $success;
        text-style: bold;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    MediaCard > .card-badge.-new {
        color: $warning;
    }
    """

    def __init__(self, item: MediaItem, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.item = item

    def compose(self):
        yield Cover(covers.cover_url(self.item), display_title(self.item))
        yield Static(classes="card-title", markup=False)
        yield Static(classes="card-meta", markup=False)
        yield Static(classes="card-badge", markup=False)

    def on_mount(self) -> None:
        self._render_text()

    def set_item(self, item: MediaItem) -> None:
        self.item = item
        self.query_one(Cover).set_url(covers.cover_url(item))
        self._render_text()

    def _render_text(self) -> None:
        item = self.item
        title = display_title(item)
        self.tooltip = title
        self.query_one(".card-title", Static).update(title)
        self.query_one(".card-meta", Static).update(meta_line(item))
        label = badge(item) or ""
        fresh = new_episodes(item)
        if fresh:
            label = f"{label} · {fresh} new" if label else f"{fresh} new"
        badge_widget = self.query_one(".card-badge", Static)
        badge_widget.update(label)
        badge_widget.set_class(bool(fresh), "-new")


class TileGrid(ScrollableContainer, can_focus=False):
    """A scrolling grid that fits as many fixed-size cells as the width allows.

    Arrow keys move focus between cells; Up on the first row moves focus to
    whatever comes before the grid (a search box or tabs).
    """

    DEFAULT_CSS = """
    TileGrid {
        layout: grid;
        grid-gutter: 1 2;
        grid-columns: 1fr;
        padding: 1 2;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("up", "move(-1, 0)", show=False),
        Binding("down", "move(1, 0)", show=False),
        Binding("left", "move(0, -1)", show=False),
        Binding("right", "move(0, 1)", show=False),
        Binding("home", "jump(0)", show=False),
        Binding("end", "jump(-1)", show=False),
    ]

    GUTTER = 2

    def __init__(
        self, *children: Widget, cell_width: int, cell_height: int, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.columns = 0

    def on_mount(self) -> None:
        self.styles.grid_rows = str(self.cell_height)  # type: ignore[assignment]
        self._fit_columns()

    def on_resize(self, event: Resize) -> None:
        self._fit_columns()

    def _fit_columns(self) -> None:
        width = self.scrollable_content_region.width or self.size.width
        columns = max(1, (width + self.GUTTER) // (self.cell_width + self.GUTTER))
        if columns != self.columns:
            self.columns = columns
            self.styles.grid_size_columns = columns

    def tiles(self) -> List[Tile]:
        return [tile for tile in self.query_children(Tile) if tile.display]

    def focus_first(self) -> bool:
        tiles = self.tiles()
        if tiles:
            tiles[0].focus()
        return bool(tiles)

    def action_jump(self, index: int) -> None:
        tiles = self.tiles()
        if tiles:
            tiles[index].focus()

    def action_move(self, rows: int, columns: int) -> None:
        tiles = self.tiles()
        if not tiles:
            return
        focused = self.screen.focused
        if focused not in tiles:
            tiles[0].focus()
            return
        index = tiles.index(focused)  # type: ignore[arg-type]
        per_row = max(1, self.columns)
        target = index + columns + rows * per_row
        if 0 <= target < len(tiles):
            tiles[target].focus()
        elif rows > 0 and index // per_row < (len(tiles) - 1) // per_row:
            # Down from a full row into a shorter last row.
            tiles[-1].focus()
        elif target < 0 and rows < 0:
            self._focus_before(tiles[0])

    def _focus_before(self, first: Tile) -> None:
        chain = self.screen.focus_chain
        if first in chain:
            position = chain.index(first)
            if position > 0:
                chain[position - 1].focus()


class MediaGrid(TileGrid):
    CARD_WIDTH = 24
    CARD_HEIGHT = 19

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            cell_width=self.CARD_WIDTH, cell_height=self.CARD_HEIGHT, **kwargs
        )

    async def show_items(self, items: List[MediaItem]) -> None:
        await self.remove_children()
        if items:
            await self.mount_all([MediaCard(item) for item in items])
        self.scroll_home(animate=False)

    def cards(self) -> List[MediaCard]:
        return list(self.query_children(MediaCard))

    def update_item(self, item: MediaItem) -> None:
        for card in self.cards():
            if card.item.id == item.id:
                card.set_item(item)


class MediaBrowser(Vertical):
    """A paged media grid fed by a loader running in a worker thread."""

    class Loaded(Message):
        def __init__(
            self, browser: "MediaBrowser", result: Optional[MediaSearchResult]
        ) -> None:
            super().__init__()
            self.browser = browser
            self.result = result

        @property
        def control(self) -> "MediaBrowser":
            return self.browser

    DEFAULT_CSS = """
    MediaBrowser {
        height: 1fr;
    }
    MediaBrowser > .browser-empty {
        display: none;
        height: 1fr;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
    }
    MediaBrowser.-empty > .browser-empty {
        display: block;
    }
    MediaBrowser.-empty > MediaGrid {
        display: none;
    }
    MediaBrowser > .browser-status {
        height: 1;
        padding: 0 2;
        color: $text-muted;
        background: $panel;
    }
    """

    BINDINGS = [
        Binding("n", "page(1)", "Next page"),
        Binding("p", "page(-1)", "Prev page"),
        Binding("r", "reload", "Refresh"),
    ]

    def __init__(
        self,
        loader: Optional[Loader] = None,
        *,
        empty_text: str = "Nothing to show here yet.",
        autoload: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.loader = loader
        self.empty_text = empty_text
        self.autoload = autoload
        self.page = 1
        self.has_next = False
        self.loaded = False

    def compose(self):
        yield MediaGrid()
        yield Static(self.empty_text, classes="browser-empty", markup=False)
        yield Static("", classes="browser-status", markup=False)

    def on_mount(self) -> None:
        if self.autoload and self.loader is not None:
            self.load(1)

    @property
    def grid(self) -> MediaGrid:
        return self.query_one(MediaGrid)

    def set_loader(self, loader: Loader, empty_text: Optional[str] = None) -> None:
        self.loader = loader
        if empty_text is not None:
            self.empty_text = empty_text
            self.query_one(".browser-empty", Static).update(empty_text)
        self.load(1)

    def load(self, page: Optional[int] = None) -> None:
        if self.loader is None:
            return
        page = page or self.page
        self.loading = True
        self._set_status(f"Loading page {page}…")
        self._fetch(self.loader, page)

    @work(thread=True, exclusive=True, group="browser")
    def _fetch(self, loader: Loader, page: int) -> None:
        error: Optional[Exception] = None
        result: Optional[MediaSearchResult] = None
        try:
            result = loader(page)
        except Exception as e:
            logger.exception("Failed to load a page of media")
            error = e
        if get_current_worker().is_cancelled:
            return
        self.app.call_from_thread(self._apply, page, result, error)

    async def _apply(
        self, page: int, result: Optional[MediaSearchResult], error: Optional[Exception]
    ) -> None:
        self.loading = False
        if error is not None:
            self._set_status(f"Could not load this page: {error}")
            self.app.notify(str(error), title="Loading failed", severity="error")
            return
        items = result.media if result else []
        self.loaded = True
        self.page = page
        self.has_next = bool(result and result.page_info.has_next_page)
        self.set_class(not items, "-empty")
        focused = self.screen.focused
        had_focus = focused is not None and self in focused.ancestors
        await self.grid.show_items(items)
        if had_focus or focused is None:
            self.grid.focus_first()
        self._set_status(self._status_text(result))
        self.post_message(self.Loaded(self, result))

    def _status_text(self, result: Optional[MediaSearchResult]) -> str:
        if not result or not result.media:
            return "No results"
        parts = [f"Page {self.page}"]
        if result.page_info.total:
            parts.append(f"{result.page_info.total:,} titles")
        hints = []
        if self.has_next:
            hints.append("n next")
        if self.page > 1:
            hints.append("p previous")
        hints.append("r refresh")
        return " · ".join(parts) + "   " + "  ".join(hints)

    def _set_status(self, text: str) -> None:
        self.query_one(".browser-status", Static).update(text)

    def action_page(self, delta: int) -> None:
        if delta > 0 and not self.has_next:
            self.app.notify("You are on the last page.", timeout=2)
            return
        if delta < 0 and self.page <= 1:
            return
        self.load(self.page + delta)

    def action_reload(self) -> None:
        self.load(self.page)

    def update_item(self, item: MediaItem) -> None:
        self.grid.update_item(item)
