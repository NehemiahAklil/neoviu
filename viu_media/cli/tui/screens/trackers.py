"""Tracker setup: tracking mode plus AniList and MyAnimeList login, like curd."""

import logging
import threading
from typing import List, Optional

from textual import on, work
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    RadioButton,
    RadioSet,
    Static,
)

from ...service.tracking import ANILIST, MYANIMELIST, TrackingError
from ...service.tracking.service import MalLoginRequest, TrackerState
from ...utils.tracker_login import MAL_WAIT_SECONDS, REMOTE_CHOICES
from .base import ViuScreen, safe_label

logger = logging.getLogger(__name__)


class TrackersScreen(ViuScreen):
    DEFAULT_CSS = """
    TrackersScreen #trackers {
        padding: 1 2;
    }
    TrackersScreen #trackers-intro {
        height: auto;
        margin-bottom: 1;
        padding: 1 2;
        border: round $accent;
    }
    TrackersScreen .section-title {
        text-style: bold;
        margin-top: 1;
    }
    TrackersScreen #remote {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    TrackersScreen #cards {
        height: auto;
    }
    TrackersScreen .card {
        width: 1fr;
        height: auto;
        margin-right: 2;
        padding: 0 2 1 2;
        border: round $primary 50%;
    }
    TrackersScreen .card.-ready {
        border: round $success;
    }
    TrackersScreen .card.-disabled {
        opacity: 60%;
    }
    TrackersScreen .card-title {
        text-style: bold;
        color: $accent;
    }
    TrackersScreen .card-status {
        height: auto;
        margin-bottom: 1;
    }
    TrackersScreen .card-help {
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }
    TrackersScreen .card Input {
        margin-bottom: 1;
    }
    TrackersScreen .card-buttons {
        height: auto;
        margin-bottom: 1;
    }
    TrackersScreen .card-buttons Button {
        margin-right: 1;
    }
    TrackersScreen #trackers-done {
        margin-top: 1;
    }
    """

    def __init__(self, intro: bool = False) -> None:
        super().__init__()
        self.intro = intro
        self._mal_request: Optional[MalLoginRequest] = None
        self._mal_cancel = threading.Event()

    def compose(self):
        tracking = self.viu.ctx.tracking
        current = tracking.remote
        port = tracking.config.tracking.mal_redirect_port
        yield Header()
        with VerticalScroll(id="trackers"):
            if self.intro:
                yield Static(
                    "[b]Welcome to neoviu![/b]\n"
                    "Log in to AniList or MyAnimeList to see your lists by status "
                    "(watching, planning, completed…) and keep your progress in sync "
                    "while you watch. You can skip this and come back with [b]t[/b] "
                    "from the home screen.",
                    id="trackers-intro",
                )
            yield Static(
                "Where should neoviu track your anime?", classes="section-title"
            )
            with RadioSet(id="remote"):
                for label, remote in REMOTE_CHOICES.items():
                    yield RadioButton(label, value=remote == current, name=remote)
            with Horizontal(id="cards"):
                with Vertical(id="anilist-card", classes="card"):
                    yield Static("AniList", classes="card-title")
                    yield Static(
                        "Checking…", id="anilist-status", classes="card-status"
                    )
                    yield Static(
                        "1. Open the login page and approve neoviu.\n"
                        "2. Copy the token AniList shows and paste it below.",
                        classes="card-help",
                    )
                    yield Input(
                        placeholder="Paste your AniList token",
                        password=True,
                        id="anilist-token",
                    )
                    with Horizontal(classes="card-buttons"):
                        yield Button("Open login page", id="anilist-open")
                        yield Button("Save token", id="anilist-save", variant="primary")
                        yield Button("Log out", id="anilist-logout", variant="error")
                with Vertical(id="mal-card", classes="card"):
                    yield Static("MyAnimeList", classes="card-title")
                    yield Static("Checking…", id="mal-status", classes="card-status")
                    yield Static(
                        "MyAnimeList needs your own API client. Create one at "
                        "https://myanimelist.net/apiconfig (App Type: other) with the "
                        f"redirect URL http://localhost:{port}/callback, then save its "
                        "client ID here.",
                        classes="card-help",
                        markup=False,
                    )
                    yield Input(
                        value=tracking.config.tracking.mal_client_id,
                        placeholder=_client_id_placeholder(tracking.mal_client_id),
                        id="mal-client-id",
                    )
                    yield Input(
                        value=tracking.config.tracking.mal_client_secret,
                        placeholder="Client secret (only for web app clients)",
                        password=True,
                        id="mal-client-secret",
                    )
                    with Horizontal(classes="card-buttons"):
                        yield Button("Save client", id="mal-save-client")
                        yield Button(
                            "Log in with browser", id="mal-login", variant="primary"
                        )
                        yield Button("Cancel", id="mal-cancel")
                    yield Input(
                        placeholder="…or paste the URL your browser was sent to",
                        id="mal-callback",
                    )
                    with Horizontal(classes="card-buttons"):
                        yield Button("Submit URL", id="mal-submit")
                        yield Button("Log out", id="mal-logout", variant="error")
            yield Button(
                "Continue" if self.intro else "Done",
                id="trackers-done",
                variant="success",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "Trackers"
        self.query_one("#mal-cancel", Button).display = False
        self.query_one(RadioSet).focus()
        self.refresh_states()

    def on_unmount(self) -> None:
        self._mal_cancel.set()

    # --- status --------------------------------------------------------------

    @work(thread=True, exclusive=True, group="tracker-states")
    def refresh_states(self) -> None:
        try:
            states = self.viu.ctx.tracking.states()
        except Exception as e:
            logger.exception("Could not read tracker status")
            self.app.call_from_thread(
                self.notify, str(e), title="Trackers unavailable", severity="error"
            )
            return
        self.app.call_from_thread(self._show_states, states)

    def _show_states(self, states: List[TrackerState]) -> None:
        for state in states:
            prefix = "anilist" if state.name == ANILIST else "mal"
            card = self.query_one(f"#{prefix}-card")
            card.set_class(state.logged_in, "-ready")
            card.set_class(not state.enabled, "-disabled")
            if state.logged_in:
                text = (
                    f"[$success]● Logged in as {safe_label(state.username) or '?'}[/]"
                )
            else:
                text = "[$warning]○ Not logged in[/]"
            if not state.enabled:
                text += "  [$text-muted](not used by the current mode)[/]"
            self.query_one(f"#{prefix}-status", Static).update(text)
            self.query_one(f"#{prefix}-logout", Button).disabled = not state.logged_in

    # --- tracking mode -------------------------------------------------------

    @on(RadioSet.Changed, "#remote")
    def _remote_changed(self, event: RadioSet.Changed) -> None:
        remote = event.pressed.name
        tracking = self.viu.ctx.tracking
        if remote is None or remote == tracking.remote:
            return
        try:
            tracking.set_remote(remote)  # type: ignore[arg-type]
        except Exception as e:
            logger.warning(f"Could not save the tracking mode: {e}")
            tracking.set_remote(remote, persist=False)  # type: ignore[arg-type]
            self.notify(
                "Applied for this session only; the config file could not be saved.",
                severity="warning",
            )
        else:
            self.notify(f"Tracking with: {event.pressed.label}")
        self.refresh_states()

    # --- AniList -------------------------------------------------------------

    @on(Button.Pressed, "#anilist-open")
    def _anilist_open(self) -> None:
        url = self.viu.ctx.tracking.anilist_login_url
        self.app.open_url(url)
        self.notify(
            "Approve neoviu, then paste the token here.",
            title="AniList login opened in your browser",
        )
        self.query_one("#anilist-token", Input).focus()

    @on(Input.Submitted, "#anilist-token")
    @on(Button.Pressed, "#anilist-save")
    def _anilist_save(self) -> None:
        token_input = self.query_one("#anilist-token", Input)
        token = token_input.value.strip()
        if not token:
            self.notify(
                "Paste the token from the AniList page first.", severity="warning"
            )
            token_input.focus()
            return
        self._anilist_login(token)

    @work(thread=True, exclusive=True, group="anilist-login")
    def _anilist_login(self, token: str) -> None:
        try:
            profile = self.viu.ctx.tracking.login_anilist(token)
        except TrackingError as e:
            self.app.call_from_thread(
                self.notify, str(e), title="AniList login failed", severity="error"
            )
            return
        except Exception as e:
            logger.exception("AniList login failed")
            self.app.call_from_thread(
                self.notify, str(e), title="AniList login failed", severity="error"
            )
            return
        self.app.call_from_thread(self._logged_in, ANILIST, profile.name)

    # --- MyAnimeList ---------------------------------------------------------

    @on(Input.Submitted, "#mal-client-id, #mal-client-secret")
    @on(Button.Pressed, "#mal-save-client")
    def _mal_save_client(self) -> bool:
        client_id = self.query_one("#mal-client-id", Input).value
        secret = self.query_one("#mal-client-secret", Input).value
        tracking = self.viu.ctx.tracking
        if not client_id.strip() and not tracking.mal_client_id:
            self.notify("Enter your MyAnimeList client ID.", severity="warning")
            return False
        if client_id.strip() == tracking.config.tracking.mal_client_id and (
            secret.strip() == tracking.config.tracking.mal_client_secret
        ):
            return True
        try:
            tracking.set_mal_credentials(client_id, secret)
        except Exception as e:
            logger.warning(f"Could not save the MyAnimeList client: {e}")
            tracking.set_mal_credentials(client_id, secret, persist=False)
            self.notify(
                "Applied for this session only; the config file could not be saved.",
                severity="warning",
            )
        else:
            self.notify("MyAnimeList client saved.")
        return True

    @on(Button.Pressed, "#mal-login")
    def _mal_login(self) -> None:
        if not self._mal_save_client():
            return
        tracking = self.viu.ctx.tracking
        try:
            request = tracking.begin_mal_login()
        except TrackingError as e:
            self.notify(str(e), title="MyAnimeList", severity="error", timeout=10)
            return
        self._mal_cancel.set()
        self._mal_cancel = threading.Event()
        self._mal_request = request
        self.app.open_url(request.url)
        self.query_one("#mal-status", Static).update(
            "[$accent]Waiting for you to approve neoviu in the browser…[/]"
        )
        self.query_one("#mal-cancel", Button).display = True
        self.notify(
            "If the browser did not open, or it cannot reach this computer, "
            "paste the final URL below.",
            title="MyAnimeList login opened in your browser",
            timeout=8,
        )
        self._mal_wait(request, self._mal_cancel)

    @work(thread=True, exclusive=True, group="mal-wait")
    def _mal_wait(self, request: MalLoginRequest, cancel: threading.Event) -> None:
        tracking = self.viu.ctx.tracking
        try:
            query = tracking.wait_for_mal_redirect(
                request, timeout=MAL_WAIT_SECONDS, cancel=cancel
            )
        except OSError as e:
            self.app.call_from_thread(
                self._mal_wait_ended,
                f"Port {request.port} is busy ({e}). Paste the redirect URL instead.",
            )
            return
        except TrackingError as e:
            self.app.call_from_thread(self._mal_wait_ended, str(e))
            return
        if query is None:
            if not cancel.is_set():
                self.app.call_from_thread(
                    self._mal_wait_ended,
                    "Timed out waiting for MyAnimeList. Paste the redirect URL instead.",
                )
            return
        self._mal_complete(request, query)

    def _mal_wait_ended(self, message: Optional[str] = None) -> None:
        self.query_one("#mal-cancel", Button).display = False
        if message:
            self.notify(message, title="MyAnimeList", severity="warning", timeout=10)
        self.refresh_states()

    @on(Button.Pressed, "#mal-cancel")
    def _mal_cancel_wait(self) -> None:
        self._mal_cancel.set()
        self._mal_wait_ended()

    @on(Input.Submitted, "#mal-callback")
    @on(Button.Pressed, "#mal-submit")
    def _mal_submit(self) -> None:
        callback = self.query_one("#mal-callback", Input).value.strip()
        if self._mal_request is None:
            self.notify(
                "Press “Log in with browser” first, then paste the URL you land on.",
                severity="warning",
            )
            return
        if not callback:
            self.notify("Paste the URL from your browser first.", severity="warning")
            return
        self._mal_cancel.set()
        self._mal_submit_worker(self._mal_request, callback)

    @work(thread=True, exclusive=True, group="mal-submit")
    def _mal_submit_worker(self, request: MalLoginRequest, callback: str) -> None:
        self._mal_complete(request, callback)

    def _mal_complete(self, request: MalLoginRequest, code_or_url: str) -> None:
        """Runs in a worker thread."""
        try:
            profile = self.viu.ctx.tracking.complete_mal_login(request, code_or_url)
        except Exception as e:
            if not isinstance(e, TrackingError):
                logger.exception("MyAnimeList login failed")
            self.app.call_from_thread(
                self.notify, str(e), title="MyAnimeList login failed", severity="error"
            )
            self.app.call_from_thread(self._mal_wait_ended)
            return
        self._mal_request = None
        self.app.call_from_thread(self._logged_in, MYANIMELIST, profile.name)

    # --- shared --------------------------------------------------------------

    def _logged_in(self, tracker: str, name: Optional[str]) -> None:
        label = "AniList" if tracker == ANILIST else "MyAnimeList"
        if tracker == ANILIST:
            self.query_one("#anilist-token", Input).value = ""
        else:
            self.query_one("#mal-callback", Input).value = ""
            self.query_one("#mal-cancel", Button).display = False
        self.notify(f"Logged in to {label} as {name or '?'}.", title="Tracker ready")
        tracking = self.viu.ctx.tracking
        if not tracking.is_enabled(tracker):
            self.notify(
                f"{label} is not used by the current tracking mode. "
                "Pick a mode above that includes it.",
                severity="warning",
            )
        self.refresh_states()

    @on(Button.Pressed, "#anilist-logout")
    def _anilist_logout(self) -> None:
        self._logout(ANILIST)

    @on(Button.Pressed, "#mal-logout")
    def _mal_logout(self) -> None:
        self._logout(MYANIMELIST)

    def _logout(self, tracker: str) -> None:
        self.viu.ctx.tracking.logout(tracker)
        self.notify("Logged out.")
        self.refresh_states()

    @on(Button.Pressed, "#trackers-done")
    def _done(self) -> None:
        self.action_back()


def _client_id_placeholder(effective: str) -> str:
    if effective:
        return "Client ID (currently set via VIU_MAL_CLIENT_ID)"
    return "Client ID"
