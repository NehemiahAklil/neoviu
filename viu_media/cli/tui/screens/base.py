"""Base screens shared by the grid TUI."""

from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from textual import on
from textual.binding import Binding
from textual.screen import Screen

from ...service.tracking import TRACKER_LABELS
from ..widgets import MediaBrowser, MediaCard, Tile

if TYPE_CHECKING:
    from ....libs.media_api.types import MediaItem
    from ..app import ViuApp


class ViuScreen(Screen):
    BINDINGS = [Binding("escape", "back", "Back")]

    @property
    def viu(self) -> "ViuApp":
        return cast("ViuApp", self.app)

    def back_result(self) -> Any:
        return None

    def action_back(self) -> None:
        self.dismiss(self.back_result())

    def report_sync(self, what: str, results: Dict[str, bool]) -> None:
        """Tells the user which trackers received a change."""
        if not results:
            self.notify(
                f"{what} saved locally. Log in to a tracker to sync it.",
                title="Not synced",
                severity="warning",
            )
            return
        synced = [TRACKER_LABELS.get(t, t) for t, ok in results.items() if ok]
        failed = [TRACKER_LABELS.get(t, t) for t, ok in results.items() if not ok]
        if synced:
            self.notify(f"{what} synced to {', '.join(synced)}.")
        if failed:
            self.notify(
                f"{what} failed on {', '.join(failed)}. Check the log for details.",
                title="Sync failed",
                severity="error",
            )


class MediaScreen(ViuScreen):
    """A screen of media cards; choosing a card opens its details."""

    @on(Tile.Chosen)
    def _open_card(self, event: Tile.Chosen) -> None:
        if isinstance(event.tile, MediaCard):
            event.stop()
            self.viu.open_media(event.tile.item, self.media_changed)

    def media_changed(self, item: "MediaItem") -> None:
        for browser in self.query(MediaBrowser):
            browser.update_item(item)


def safe_label(value: Optional[str]) -> str:
    from textual.markup import escape

    return escape(value or "")
