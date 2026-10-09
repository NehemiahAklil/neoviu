"""The home screen: a grid of menu tiles plus tracker status."""

import logging
from typing import TYPE_CHECKING, List

from textual import on, work
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from ...service.tracking import TRACKER_LABELS
from ..catalog import (
    HOME_ENTRIES,
    SORTED_TILES,
    continue_loader,
    random_loader,
    recent_loader,
)
from ..widgets import MenuTile, Tile, TileGrid
from .base import ViuScreen, safe_label

if TYPE_CHECKING:
    from ...service.tracking.service import TrackerState

logger = logging.getLogger(__name__)

LOGO = "\n".join(
    [
        "┏┓╻ ┏━╸ ┏━┓ ╻ ╻ ╻ ╻ ╻",
        "┃┗┫ ┣╸  ┃ ┃ ┃┏┛ ┃ ┃ ┃",
        "╹ ╹ ┗━╸ ┗━┛ ┗┛  ╹ ┗━┛",
    ]
)


class HomeScreen(ViuScreen):
    DEFAULT_CSS = """
    HomeScreen #home-top {
        height: 5;
        padding: 1 3 0 3;
    }
    HomeScreen #logo {
        width: auto;
        color: $accent;
        text-style: bold;
    }
    HomeScreen #tagline {
        width: 1fr;
        padding: 1 0 0 3;
        color: $text-muted;
    }
    HomeScreen #tracker-status {
        width: auto;
        min-width: 30;
        text-align: right;
    }
    """

    BINDINGS = [
        Binding("escape", "noop", show=False),
        Binding("slash", "open('search')", "Search"),
        Binding("l", "open('library')", "Library"),
        Binding("c", "open('continue')", "Continue"),
        Binding("t", "open('trackers')", "Trackers"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._first_show = True

    def compose(self):
        yield Header()
        with Horizontal(id="home-top"):
            yield Static(LOGO, id="logo", markup=False)
            yield Static("anime in your terminal", id="tagline", markup=False)
            yield Static("Checking trackers…", id="tracker-status")
        yield TileGrid(
            *[MenuTile(entry) for entry in HOME_ENTRIES],
            cell_width=26,
            cell_height=5,
            id="home-grid",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(TileGrid).focus_first()

    def on_screen_resume(self) -> None:
        prompt = self._first_show
        self._first_show = False
        self.refresh_trackers(prompt)

    def action_noop(self) -> None:
        pass

    @work(thread=True, exclusive=True, group="trackers")
    def refresh_trackers(self, prompt: bool = False) -> None:
        tracking = self.viu.ctx.tracking
        try:
            states = tracking.states()
            missing = tracking.missing_logins()
        except Exception as e:
            logger.exception("Could not read tracker status")
            self.app.call_from_thread(
                self.query_one("#tracker-status", Static).update,
                f"[$error]Trackers unavailable:[/] {safe_label(str(e))}",
            )
            return
        self.app.call_from_thread(self._show_trackers, states, missing, prompt)

    def _show_trackers(
        self, states: List["TrackerState"], missing: List[str], prompt: bool
    ) -> None:
        lines = []
        for state in states:
            if not state.enabled:
                continue
            if state.logged_in:
                who = safe_label(state.username) or "logged in"
                lines.append(f"[b]{state.label}[/b] [$success]● {who}[/]")
            else:
                lines.append(f"[b]{state.label}[/b] [$warning]○ not logged in[/]")
        if not lines:
            lines.append("[$text-muted]Local tracking only[/]")
        lines.append("[$text-muted]t · manage trackers[/]")
        self.query_one("#tracker-status", Static).update("\n".join(lines))

        tracking = self.viu.ctx.tracking
        if (
            prompt
            and missing
            and tracking.config.tracking.prompt_login
            and "tui" not in tracking.prompted
        ):
            tracking.prompted.add("tui")
            names = " and ".join(TRACKER_LABELS[t] for t in missing)
            self.notify(f"You are not logged in to {names}.", title="Trackers")
            from .trackers import TrackersScreen

            self.app.push_screen(TrackersScreen(intro=True))

    @on(Tile.Chosen)
    def _chosen(self, event: Tile.Chosen) -> None:
        if isinstance(event.tile, MenuTile):
            event.stop()
            self.action_open(event.tile.entry.key)

    def action_open(self, key: str) -> None:
        from .browse import BrowseScreen, LibraryScreen, SearchScreen
        from .trackers import TrackersScreen

        ctx = self.viu.ctx
        titles = {entry.key: entry.title for entry in HOME_ENTRIES}
        if key == "continue":
            self.app.push_screen(
                BrowseScreen(
                    titles[key],
                    continue_loader(ctx),
                    empty_text="Nothing in progress yet. Find something in Trending!",
                )
            )
        elif key == "library":
            self.app.push_screen(LibraryScreen())
        elif key == "search":
            self.app.push_screen(SearchScreen())
        elif key in SORTED_TILES:
            from ..catalog import sorted_loader

            self.app.push_screen(BrowseScreen(titles[key], sorted_loader(ctx, key)))
        elif key == "recent":
            self.app.push_screen(
                BrowseScreen(
                    titles[key],
                    recent_loader(ctx),
                    empty_text="You have not watched anything with neoviu yet.",
                )
            )
        elif key == "random":
            self.app.push_screen(BrowseScreen(titles[key], random_loader(ctx)))
        elif key == "trackers":
            self.app.push_screen(TrackersScreen())
        elif key == "classic":
            self.viu.run_classic()
        elif key == "quit":
            self.app.exit()
