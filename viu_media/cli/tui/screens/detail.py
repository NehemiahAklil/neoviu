"""Anime details with tracker-synced list actions."""

import logging
import threading
from typing import Dict, List, Optional

from textual import on, work
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from ....libs.media_api.types import MediaItem, UserListItem, UserMediaListStatus
from ...service.tracking import ANILIST, TRACKER_LABELS
from .. import covers
from ..catalog import load_item_state, with_local_status
from ..formatting import (
    STATUS_LABELS,
    STATUS_ORDER,
    airing_text,
    alt_title,
    badge,
    display_title,
    format_label,
    progress_text,
    score_label,
    season_text,
    strip_html,
)
from ..widgets import Cover
from .base import ViuScreen, safe_label
from .dialogs import ChoiceDialog, ConfirmDialog, InputDialog, score_validator

logger = logging.getLogger(__name__)


class DetailScreen(ViuScreen):
    DEFAULT_CSS = """
    DetailScreen #detail-body {
        height: 1fr;
        padding: 1 2;
    }
    DetailScreen #detail-cover {
        width: 40;
        height: 1fr;
        margin-right: 2;
        align: center top;
    }
    DetailScreen #detail-info {
        width: 1fr;
        height: 1fr;
        scrollbar-size-vertical: 1;
    }
    DetailScreen #detail-title {
        text-style: bold;
        color: $accent;
    }
    DetailScreen #detail-alt {
        color: $text-muted;
    }
    DetailScreen .detail-line {
        height: auto;
    }
    DetailScreen #detail-meta {
        margin-top: 1;
    }
    DetailScreen #detail-tracking {
        height: auto;
        margin-top: 1;
        padding: 0 1;
        border: round $primary 50%;
    }
    DetailScreen #detail-actions {
        height: auto;
        margin-top: 1;
    }
    DetailScreen #detail-actions Button {
        min-width: 10;
        margin-right: 1;
    }
    DetailScreen #detail-description {
        height: auto;
        margin-top: 1;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("p", "play", "Play"),
        Binding("e", "episodes", "Episodes"),
        Binding("s", "status", "Status"),
        Binding("plus,equals_sign", "progress(1)", "+1 ep"),
        Binding("minus", "progress(-1)", "-1 ep"),
        Binding("c", "score", "Score"),
        Binding("x,delete", "remove", "Remove"),
        Binding("o", "open_site", "Open site"),
        Binding("t", "trackers", "Trackers", show=False),
        Binding("r", "refresh", "Refresh", show=False),
    ]

    def __init__(self, item: MediaItem) -> None:
        super().__init__()
        self.item = item
        self.entries: Dict[str, Optional[UserListItem]] = {}
        self.trackers: List[str] = []
        self.logged_in: Dict[str, bool] = {}
        self.changed = False
        self._write_lock = threading.Lock()

    def compose(self):
        yield Header()
        with Horizontal(id="detail-body"):
            yield Cover(
                covers.cover_url(self.item, large=True),
                display_title(self.item),
                id="detail-cover",
            )
            with VerticalScroll(id="detail-info"):
                yield Static(id="detail-title", classes="detail-line", markup=False)
                yield Static(id="detail-alt", classes="detail-line", markup=False)
                yield Static(id="detail-meta", classes="detail-line", markup=False)
                yield Static(id="detail-genres", classes="detail-line", markup=False)
                yield Static(id="detail-airing", classes="detail-line", markup=False)
                yield Static("Loading your list status…", id="detail-tracking")
                with Horizontal(id="detail-actions"):
                    yield Button("▶ Play", id="play", variant="primary")
                    yield Button("Episodes", id="episodes")
                    yield Button("Status", id="status")
                    yield Button("−1", id="minus")
                    yield Button("+1", id="plus")
                    yield Button("Score", id="score")
                    yield Button("Remove", id="remove", variant="error")
                    yield Button("Open site", id="open-site")
                yield Static(
                    id="detail-description", classes="detail-line", markup=False
                )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = display_title(self.item)
        self._render_item()
        self.query_one("#play", Button).focus()
        self.reload()

    def back_result(self) -> Optional[MediaItem]:
        return self.item if self.changed else None

    # --- loading -------------------------------------------------------------

    @work(thread=True, exclusive=True, group="detail-load")
    def reload(self) -> None:
        ctx = self.viu.ctx
        try:
            item, entries = load_item_state(ctx, self.item)
            tracking = ctx.tracking
            trackers = tracking.enabled_trackers
            logged_in = {t: tracking.is_logged_in(t) for t in trackers}
        except Exception as e:
            logger.exception("Could not load the anime details")
            self.app.call_from_thread(
                self.notify, str(e), title="Could not refresh", severity="error"
            )
            return
        self.app.call_from_thread(self._apply_state, item, entries, trackers, logged_in)

    def _apply_state(
        self,
        item: MediaItem,
        entries: Dict[str, Optional[UserListItem]],
        trackers: List[str],
        logged_in: Dict[str, bool],
    ) -> None:
        self.item = item
        self.entries = entries
        self.trackers = trackers
        self.logged_in = logged_in
        self._render_item()

    def _set_item(self, item: MediaItem) -> None:
        self.item = item
        self.changed = True
        self._render_item()

    # --- rendering -----------------------------------------------------------

    def _render_item(self) -> None:
        item = self.item
        self.query_one(Cover).set_url(covers.cover_url(item, large=True))
        self.query_one("#detail-title", Static).update(display_title(item))
        self._set_line("#detail-alt", alt_title(item))

        meta = [
            format_label(item),
            f"{item.episodes} episodes" if item.episodes else "",
            f"{item.duration} min" if item.duration else "",
            item.status.value.replace("_", " ").title() if item.status else "",
            season_text(item) or "",
            score_label(item) or "",
            f"♥ {item.popularity:,}" if item.popularity else "",
        ]
        self.query_one("#detail-meta", Static).update(" · ".join(p for p in meta if p))

        genres = ", ".join(genre.value for genre in item.genres)
        studios = ", ".join(
            studio.name
            for studio in item.studios
            if studio.name and studio.is_animation_studio is not False
        )
        lines = [
            line for line in (genres, f"Studio: {studios}" if studios else "") if line
        ]
        self._set_line("#detail-genres", "\n".join(lines))
        self._set_line("#detail-airing", airing_text(item))

        self.query_one("#detail-tracking", Static).update(self._tracking_text())
        entry = item.user_status
        started = bool(
            entry and entry.progress and entry.status != UserMediaListStatus.COMPLETED
        )
        self.query_one("#play", Button).label = "▶ Continue" if started else "▶ Play"
        self.query_one("#remove", Button).disabled = not any(
            self.entries.get(t) for t in self.trackers
        )
        self.query_one("#detail-description", Static).update(
            strip_html(item.description) or "No description available."
        )

    def _set_line(self, selector: str, text: Optional[str]) -> None:
        line = self.query_one(selector, Static)
        line.update(text or "")
        line.display = bool(text)

    def _tracking_text(self) -> str:
        item = self.item
        if not self.trackers:
            local = with_local_status(item, self.viu.ctx.media_registry).user_status
            text = badge(item, local) if local else None
            return (
                f"[b]Local[/b]  {safe_label(text or 'Not watched yet')}\n"
                "[$text-muted]Tracking is local only · press t to set up AniList or MyAnimeList[/]"
            )
        lines = []
        for tracker in self.trackers:
            label = TRACKER_LABELS[tracker]
            if not self.logged_in.get(tracker):
                lines.append(
                    f"[b]{label}[/b]  [$warning]not logged in · press t to log in[/]"
                )
                continue
            entry = self.entries.get(tracker)
            if entry is None or entry.status is None:
                lines.append(f"[b]{label}[/b]  [$text-muted]not on your list[/]")
                continue
            parts = [
                STATUS_LABELS.get(entry.status, entry.status.value.title()),
                f"{progress_text(item, entry)} episodes",
            ]
            if entry.score:
                parts.append(f"scored {entry.score:g}")
            lines.append(f"[b]{label}[/b]  [$success]{' · '.join(parts)}[/]")
        return "\n".join(lines)

    # --- actions -------------------------------------------------------------

    @on(Button.Pressed)
    def _button(self, event: Button.Pressed) -> None:
        actions = {
            "play": self.action_play,
            "episodes": self.action_episodes,
            "status": self.action_status,
            "minus": lambda: self.action_progress(-1),
            "plus": lambda: self.action_progress(1),
            "score": self.action_score,
            "remove": self.action_remove,
            "open-site": self.action_open_site,
        }
        if action := actions.get(event.button.id or ""):
            event.stop()
            action()

    def action_play(self) -> None:
        self._play(episodes=False)

    def action_episodes(self) -> None:
        self._play(episodes=True)

    def _play(self, episodes: bool) -> None:
        if self.viu.play(self.item, episodes=episodes):
            # Playback may have moved progress or the list status.
            self.changed = True
            self.reload()

    def action_status(self) -> None:
        entry = self.item.user_status
        current = entry.status.value if entry and entry.status else None
        options = [(status.value, STATUS_LABELS[status]) for status in STATUS_ORDER]

        def chosen(value: Optional[str]) -> None:
            if value and value != current:
                self._set_status(UserMediaListStatus(value))

        self.app.push_screen(
            ChoiceDialog(
                f"Set list status · {display_title(self.item)}", options, current
            ),
            chosen,
        )

    @work(thread=True, group="detail-write")
    def _set_status(self, status: UserMediaListStatus) -> None:
        with self._write_lock:
            item = self.item
            progress = None
            if status == UserMediaListStatus.COMPLETED and item.episodes:
                progress = str(item.episodes)
            results = self.viu.ctx.watch_history.update(
                item, progress=progress, status=status
            )
            self._optimistic(status=status, progress=progress)
            self.app.call_from_thread(
                self.report_sync, f"Status “{STATUS_LABELS[status]}”", results
            )
        self.app.call_from_thread(self.reload)

    def action_progress(self, delta: int) -> None:
        self._step_progress(delta)

    @work(thread=True, group="detail-write")
    def _step_progress(self, delta: int) -> None:
        with self._write_lock:
            item = self.item
            progress, status, results = self.viu.ctx.watch_history.step_progress(
                item, delta
            )
            self._optimistic(status=status, progress=str(progress))
            what = f"Episode {progress}" if progress else "Progress reset"
            self.app.call_from_thread(self.report_sync, what, results)
        self.app.call_from_thread(self.reload)

    def action_score(self) -> None:
        entry = self.item.user_status
        current = f"{entry.score:g}" if entry and entry.score else ""

        def chosen(value: Optional[str]) -> None:
            if value is not None:
                self._set_score(float(value or 0))

        self.app.push_screen(
            InputDialog(
                "Your score",
                message="Rate it from 0 to 10. Enter 0 to clear your score.",
                value=current,
                placeholder="e.g. 8.5",
                validate=lambda v: score_validator(v or "0"),
            ),
            chosen,
        )

    @work(thread=True, group="detail-write")
    def _set_score(self, score: float) -> None:
        with self._write_lock:
            results = self.viu.ctx.watch_history.update(self.item, score=score)
            self._optimistic(score=score)
            self.app.call_from_thread(self.report_sync, f"Score {score:g}", results)
        self.app.call_from_thread(self.reload)

    def action_remove(self) -> None:
        listed = [TRACKER_LABELS[t] for t in self.trackers if self.entries.get(t)]
        if not listed:
            self.notify("This anime is not on any of your tracker lists.")
            return

        def confirmed(yes: Optional[bool]) -> None:
            if yes:
                self._remove()

        self.app.push_screen(
            ConfirmDialog(
                f"Remove {display_title(self.item)}?",
                f"This deletes the entry from {' and '.join(listed)}.",
                confirm="Remove",
            ),
            confirmed,
        )

    @work(thread=True, group="detail-write")
    def _remove(self) -> None:
        with self._write_lock:
            results = self.viu.ctx.tracking.delete(self.item)
            item = self.item.model_copy(update={"user_status": None})
            self.app.call_from_thread(self._set_item, item)
            self.app.call_from_thread(self.report_sync, "Removal", results)
        self.app.call_from_thread(self.reload)

    def _optimistic(
        self,
        status: Optional[UserMediaListStatus] = None,
        progress: Optional[str] = None,
        score: Optional[float] = None,
    ) -> None:
        """Shows a change right away; the follow-up reload confirms it."""
        entry = self.item.user_status or UserListItem()
        update: Dict[str, object] = {}
        if status is not None:
            update["status"] = status
        if progress is not None:
            update["progress"] = int(progress)
        if score is not None:
            update["score"] = score
        item = self.item.model_copy(
            update={"user_status": entry.model_copy(update=update)}
        )
        self.app.call_from_thread(self._set_item, item)

    def action_open_site(self) -> None:
        item = self.item
        if self.viu.ctx.config.general.media_api == ANILIST:
            url = f"https://anilist.co/anime/{item.id}"
        elif item.id_mal:
            url = f"https://myanimelist.net/anime/{item.id_mal}"
        else:
            url = f"https://myanimelist.net/anime/{item.id}"
        self.app.open_url(url)
        self.notify(url, title="Opening in your browser", timeout=4)

    def action_trackers(self) -> None:
        from .trackers import TrackersScreen

        def closed(_: object) -> None:
            self.reload()

        self.app.push_screen(TrackersScreen(), closed)

    def action_refresh(self) -> None:
        self.reload()
