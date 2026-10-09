"""Media grids: category browsing, search and the tracker-backed library."""

import logging
from typing import Optional

from textual import on, work
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Static,
    TabbedContent,
    TabPane,
    Tabs,
)

from ....libs.media_api.types import MediaItem, UserMediaListStatus
from ...service.tracking import ANILIST, MYANIMELIST, TRACKER_LABELS
from ..catalog import Loader, search_loader, user_list_loader
from ..formatting import STATUS_LABELS, STATUS_ORDER
from ..widgets import MediaBrowser
from .base import MediaScreen, safe_label

logger = logging.getLogger(__name__)

NOTE_CSS = """
.screen-note {
    height: auto;
    padding: 0 2;
    color: $text-muted;
}
"""


class BrowseScreen(MediaScreen):
    def __init__(
        self, title: str, loader: Loader, empty_text: str = "Nothing to show here."
    ) -> None:
        super().__init__()
        self.browse_title = title
        self.loader = loader
        self.empty_text = empty_text

    def compose(self):
        yield Header()
        yield MediaBrowser(self.loader, empty_text=self.empty_text)
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = self.browse_title


class SearchScreen(MediaScreen):
    DEFAULT_CSS = """
    SearchScreen #search-input {
        margin: 1 2 0 2;
    }
    """

    BINDINGS = [Binding("slash", "focus_search", "Search")]

    def compose(self):
        yield Header()
        yield Input(
            placeholder="Search anime by title, then press Enter", id="search-input"
        )
        yield MediaBrowser(
            autoload=False, empty_text="Type a title above and press Enter."
        )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "Search"
        self.query_one(Input).focus()

    @on(Input.Submitted, "#search-input")
    def _search(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        self.sub_title = f"Search · {query}"
        self.query_one(MediaBrowser).set_loader(
            search_loader(self.viu.ctx, query=query),
            empty_text=f"No anime found for “{query}”.",
        )

    @on(MediaBrowser.Loaded)
    def _loaded(self, event: MediaBrowser.Loaded) -> None:
        if isinstance(self.focused, Input):
            event.browser.grid.focus_first()

    def action_focus_search(self) -> None:
        self.query_one(Input).focus()


class LibraryScreen(MediaScreen):
    """The user's tracker lists, one tab per status, like curd's categories."""

    DEFAULT_CSS = (
        NOTE_CSS
        + """
    LibraryScreen #library-source {
        padding: 1 2 0 2;
    }
    LibraryScreen #library-tabs {
        height: 1fr;
    }
    LibraryScreen #library-tabs ContentSwitcher {
        height: 1fr;
    }
    LibraryScreen #library-tabs TabPane {
        height: 1fr;
        padding: 0;
    }
    LibraryScreen #library-login {
        height: auto;
        margin: 2 4;
        padding: 1 2;
        border: round $warning;
    }
    LibraryScreen #library-login Button {
        margin-top: 1;
    }
    LibraryScreen.-no-source #library-tabs {
        display: none;
    }
    LibraryScreen #library-login {
        display: none;
    }
    LibraryScreen.-no-source #library-login {
        display: block;
    }
    """
    )

    BINDINGS = [
        Binding("left_square_bracket", "cycle_tab(-1)", "Prev list"),
        Binding("right_square_bracket", "cycle_tab(1)", "Next list"),
        Binding("t", "trackers", "Trackers"),
        *[
            Binding(str(i), f"show_tab({i - 1})", show=False)
            for i in range(1, len(STATUS_ORDER) + 1)
        ],
    ]

    def __init__(self) -> None:
        super().__init__()
        self.source: Optional[str] = None

    def compose(self):
        ctx = self.viu.ctx
        yield Header()
        yield Static(
            "Checking your trackers…", id="library-source", classes="screen-note"
        )
        with Vertical(id="library-login"):
            yield Static(id="library-login-text")
            yield Button("Set up trackers", id="open-trackers", variant="primary")
        with TabbedContent(id="library-tabs"):
            for status in STATUS_ORDER:
                label = STATUS_LABELS[status]
                with TabPane(label, id=_tab_id(status)):
                    yield MediaBrowser(
                        user_list_loader(ctx, status),
                        autoload=False,
                        empty_text=f"Your {label} list is empty.",
                    )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "My Library"

    def on_screen_resume(self) -> None:
        self.check_source()

    @work(thread=True, exclusive=True, group="library")
    def check_source(self) -> None:
        tracking = self.viu.ctx.tracking
        try:
            source = tracking.list_source
            enabled = tracking.enabled_trackers
            username = tracking.username(source) if source else None
        except Exception as e:
            logger.exception("Could not check the list source")
            self.app.call_from_thread(
                self.notify, str(e), title="Trackers unavailable", severity="error"
            )
            source, enabled, username = None, [], None
        self.app.call_from_thread(self._apply_source, source, enabled, username)

    def _apply_source(
        self, source: Optional[str], enabled: list, username: Optional[str]
    ) -> None:
        changed = source != self.source
        self.source = source
        self.set_class(source is None, "-no-source")
        note = self.query_one("#library-source", Static)
        if source is None:
            if enabled:
                names = " or ".join(TRACKER_LABELS[t] for t in enabled)
                text = f"Log in to {names} to see your lists here and sync progress."
            else:
                text = (
                    "Tracking is set to local only. Choose AniList or MyAnimeList "
                    "to see your lists here."
                )
            self.query_one("#library-login-text", Static).update(text)
            note.update("")
            self.query_one("#open-trackers", Button).focus()
            return
        who = f" ({safe_label(username)})" if username else ""
        text = f"Showing your [b]{TRACKER_LABELS[source]}[/b] lists{who}."
        if source == ANILIST and MYANIMELIST in enabled:
            text += " Changes also sync to MyAnimeList."
        text += "  [ ] switch lists · 1-6 jump"
        note.update(text)
        if changed:
            for browser in self.query(MediaBrowser):
                browser.loaded = False
        self._load_active()

    def _load_active(self) -> None:
        tabs = self.query_one(TabbedContent)
        if not tabs.active or self.source is None:
            return
        browser = tabs.get_pane(tabs.active).query_one(MediaBrowser)
        if not browser.loaded:
            browser.load(1)

    @on(TabbedContent.TabActivated)
    def _tab_activated(self) -> None:
        self._load_active()

    @on(MediaBrowser.Loaded)
    def _loaded(self, event: MediaBrowser.Loaded) -> None:
        if self.focused is None or isinstance(self.focused, Tabs):
            event.browser.grid.focus_first()

    def action_show_tab(self, index: int) -> None:
        if 0 <= index < len(STATUS_ORDER):
            self.query_one(TabbedContent).active = _tab_id(STATUS_ORDER[index])

    def action_cycle_tab(self, delta: int) -> None:
        tabs = self.query_one(TabbedContent)
        ids = [_tab_id(status) for status in STATUS_ORDER]
        current = ids.index(tabs.active) if tabs.active in ids else 0
        tabs.active = ids[(current + delta) % len(ids)]

    def action_trackers(self) -> None:
        from .trackers import TrackersScreen

        self.app.push_screen(TrackersScreen())

    @on(Button.Pressed, "#open-trackers")
    def _open_trackers(self) -> None:
        self.action_trackers()

    def media_changed(self, item: MediaItem) -> None:
        # A status change can move the item to another list, so refresh them.
        tabs = self.query_one(TabbedContent)
        for pane in tabs.query(TabPane):
            browser = pane.query_one(MediaBrowser)
            if pane.id == tabs.active:
                browser.load()
            else:
                browser.loaded = False


def _tab_id(status: UserMediaListStatus) -> str:
    return f"list-{status.value}"
