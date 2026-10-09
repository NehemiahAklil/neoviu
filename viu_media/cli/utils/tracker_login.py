"""Interactive tracker login and mode prompts shared by the CLI menus.

Mirrors curd's first-run flow: pick where progress is tracked, then log in
to each enabled site through the browser.
"""

import logging
import webbrowser
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from ...libs.selectors.base import BaseSelector
    from ..service.feedback import FeedbackService
    from ..service.tracking import TrackingService
    from ..service.tracking.service import RemoteMode

logger = logging.getLogger(__name__)

REMOTE_CHOICES: Dict[str, "RemoteMode"] = {
    "AniList": "anilist",
    "MyAnimeList": "myanimelist",
    "AniList + MyAnimeList": "both",
    "Local only (no syncing)": "none",
}

MAL_WAIT_SECONDS = 180
MAL_APP_URL = "https://myanimelist.net/apiconfig"


def choose_remote(
    tracking: "TrackingService",
    selector: "BaseSelector",
    feedback: "FeedbackService",
) -> bool:
    """Asks where progress should be tracked and saves the answer."""
    choice = selector.choose("Where should viu track your anime?", list(REMOTE_CHOICES))
    if not choice:
        return False
    remote = REMOTE_CHOICES[choice]
    try:
        tracking.set_remote(remote)
    except Exception as e:
        tracking.set_remote(remote, persist=False)
        feedback.warning("Tracking mode applied for this session only", str(e))
    else:
        feedback.success(f"Tracking with: {choice}")
    return True


def login_anilist(
    tracking: "TrackingService",
    selector: "BaseSelector",
    feedback: "FeedbackService",
    token: Optional[str] = None,
) -> bool:
    from ..service.tracking import TrackingError

    if not token:
        url = tracking.anilist_login_url
        if webbrowser.open(url, new=2):
            feedback.info("Your browser has been opened to authorize viu on AniList.")
        else:
            feedback.warning(f"Open this page to authorize viu on AniList: {url}")
        feedback.info("Copy the access token AniList shows you and paste it below.")
        token = selector.ask("AniList access token")
    if not token:
        feedback.warning("AniList login cancelled.")
        return False
    try:
        profile = tracking.login_anilist(token)
    except TrackingError as e:
        feedback.error("AniList login failed", str(e))
        return False
    feedback.success(f"Logged in to AniList as {profile.name}")
    return True


def ask_mal_client(
    tracking: "TrackingService",
    selector: "BaseSelector",
    feedback: "FeedbackService",
) -> bool:
    """Asks for the user's own MyAnimeList API client and saves it."""
    feedback.info(
        "MyAnimeList needs your own API client ID.",
        f"Create an app at {MAL_APP_URL} (App Type: other) with the redirect "
        f"URL {tracking.mal_redirect_uri}, then paste its client ID here.",
    )
    client_id = (selector.ask("MyAnimeList client ID") or "").strip()
    if not client_id:
        return False
    secret = (
        selector.ask("Client secret (leave empty if there is none)") or ""
    ).strip()
    try:
        tracking.set_mal_credentials(client_id, secret)
    except Exception as e:
        tracking.set_mal_credentials(client_id, secret, persist=False)
        feedback.warning("MyAnimeList client saved for this session only", str(e))
    return True


def login_myanimelist(
    tracking: "TrackingService",
    selector: "BaseSelector",
    feedback: "FeedbackService",
    callback: Optional[str] = None,
) -> bool:
    from ..service.tracking import TrackingError

    if not tracking.mal_client_id and not ask_mal_client(tracking, selector, feedback):
        feedback.warning("MyAnimeList login cancelled.")
        return False
    try:
        request = tracking.begin_mal_login()
    except TrackingError as e:
        feedback.error("MyAnimeList login unavailable", str(e))
        return False

    if not callback:
        if webbrowser.open(request.url, new=2):
            feedback.info(
                "Your browser has been opened to authorize viu on MyAnimeList."
            )
        else:
            feedback.warning(f"Open this page to authorize viu: {request.url}")
        try:
            with feedback.progress(
                "Waiting for MyAnimeList (Ctrl+C to paste the redirect URL instead)",
                transient=True,
            ):
                callback = tracking.wait_for_mal_redirect(request, MAL_WAIT_SECONDS)
        except KeyboardInterrupt:
            callback = None
        except OSError as e:
            feedback.warning(
                f"Could not listen on port {request.port} for the login redirect",
                str(e),
            )
            callback = None
        except TrackingError as e:
            feedback.error("MyAnimeList login failed", str(e))
            return False
        if not callback:
            feedback.info(
                "If the page failed to load, copy its full URL from the address bar."
            )
            callback = selector.ask("Paste the redirect URL (or just the code)")
    if not callback:
        feedback.warning("MyAnimeList login cancelled.")
        return False
    try:
        with feedback.progress("Logging in to MyAnimeList", transient=True):
            profile = tracking.complete_mal_login(request, callback)
    except TrackingError as e:
        feedback.error("MyAnimeList login failed", str(e))
        return False
    feedback.success(f"Logged in to MyAnimeList as {profile.name}")
    return True


def login(
    tracker: str,
    tracking: "TrackingService",
    selector: "BaseSelector",
    feedback: "FeedbackService",
) -> bool:
    from ..service.tracking import ANILIST

    if tracker == ANILIST:
        return login_anilist(tracking, selector, feedback)
    return login_myanimelist(tracking, selector, feedback)


def ensure_tracking(
    tracking: "TrackingService",
    selector: "BaseSelector",
    feedback: "FeedbackService",
) -> bool:
    """Makes sure at least one remote tracker is usable, prompting like curd.

    Returns True when lists can be read and updates will reach a site.
    """
    from ..service.tracking import TRACKER_LABELS

    if tracking.can_track and not tracking.missing_logins():
        return True
    if not tracking.config.tracking.prompt_login:
        if not tracking.can_track:
            feedback.warning(
                "No tracker is logged in.", "Run 'viu tracker login' to connect one."
            )
        return tracking.can_track

    # Each prompt is shown once per session so declining does not nag.
    prompted = tracking.prompted
    if not tracking.enabled_trackers and "remote" not in prompted:
        prompted.add("remote")
        feedback.info("Progress is only tracked locally right now.")
        if not choose_remote(tracking, selector, feedback):
            return False

    for tracker in tracking.missing_logins():
        if tracker in prompted:
            continue
        prompted.add(tracker)
        label = TRACKER_LABELS[tracker]
        if selector.confirm(
            f"You are not logged in to {label}. Log in now?", default=True
        ):
            login(tracker, tracking, selector, feedback)
    return tracking.can_track
