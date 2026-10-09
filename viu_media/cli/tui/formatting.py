"""Plain-text helpers that turn media data into short labels for the grid TUI."""

import html
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ...libs.media_api.types import (
    MediaItem,
    MediaStatus,
    UserListItem,
    UserMediaListStatus,
)

STATUS_LABELS: Dict[UserMediaListStatus, str] = {
    UserMediaListStatus.WATCHING: "Watching",
    UserMediaListStatus.PLANNING: "Planning",
    UserMediaListStatus.COMPLETED: "Completed",
    UserMediaListStatus.PAUSED: "Paused",
    UserMediaListStatus.DROPPED: "Dropped",
    UserMediaListStatus.REPEATING: "Rewatching",
}

# Library tab order, matching how curd and the trackers group a list.
STATUS_ORDER: List[UserMediaListStatus] = list(STATUS_LABELS)

_TAG_RE = re.compile(r"<[^>]+>")
_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def display_title(item: MediaItem) -> str:
    title = item.title
    return title.english or title.romaji or title.native or f"#{item.id}"


def alt_title(item: MediaItem) -> Optional[str]:
    """The romaji (or native) title when it differs from the display title."""
    shown = display_title(item)
    for candidate in (item.title.romaji, item.title.native):
        if candidate and candidate != shown:
            return candidate
    return None


def format_label(item: MediaItem) -> str:
    if not item.format:
        return ""
    value = item.format.value
    return value if value in ("TV", "OVA", "ONA") else value.replace("_", " ").title()


def score_label(item: MediaItem) -> Optional[str]:
    """AniList's 0-100 average score shown on a 10-point scale."""
    if item.average_score is None:
        return None
    return f"★ {item.average_score / 10:.1f}"


def meta_line(item: MediaItem) -> str:
    parts: List[str] = []
    if fmt := format_label(item):
        parts.append(fmt)
    if item.episodes:
        parts.append(f"{item.episodes} ep")
    elif item.status == MediaStatus.RELEASING:
        parts.append("Airing")
    if score := score_label(item):
        parts.append(score)
    return " · ".join(parts)


def status_label(entry: Optional[UserListItem]) -> Optional[str]:
    if entry is None or entry.status is None:
        return None
    return STATUS_LABELS.get(entry.status, entry.status.value.title())


def progress_text(item: MediaItem, entry: Optional[UserListItem] = None) -> str:
    entry = entry if entry is not None else item.user_status
    watched = (entry.progress if entry else None) or 0
    return f"{watched}/{item.episodes or '?'}"


def badge(item: MediaItem, entry: Optional[UserListItem] = None) -> Optional[str]:
    """A short list badge such as ``Watching 5/12``."""
    entry = entry if entry is not None else item.user_status
    label = status_label(entry)
    if label is None:
        return None
    if entry and entry.status in (
        UserMediaListStatus.PLANNING,
        UserMediaListStatus.COMPLETED,
    ):
        return label
    return f"{label} {progress_text(item, entry)}"


def new_episodes(item: MediaItem) -> int:
    """Aired episodes the user has not watched yet, for shows being followed."""
    entry = item.user_status
    if (
        item.status != MediaStatus.RELEASING
        or item.next_airing is None
        or entry is None
        or entry.status
        not in (UserMediaListStatus.WATCHING, UserMediaListStatus.REPEATING)
    ):
        return 0
    return max(0, item.next_airing.episode - 1 - (entry.progress or 0))


def next_episode(item: MediaItem, entry: Optional[UserListItem] = None) -> int:
    """The episode a "Continue" action should start from."""
    entry = entry if entry is not None else item.user_status
    progress = (entry.progress if entry else None) or 0
    if entry and entry.status == UserMediaListStatus.COMPLETED:
        return 1
    if item.episodes:
        return min(progress + 1, item.episodes)
    return progress + 1


def airing_text(item: MediaItem, now: Optional[datetime] = None) -> Optional[str]:
    airing = item.next_airing
    if airing is None:
        return None
    if airing.airing_at is None:
        return f"Episode {airing.episode} is next"
    now = now or datetime.now(timezone.utc)
    airing_at = airing.airing_at
    if airing_at.tzinfo is None:
        airing_at = airing_at.replace(tzinfo=timezone.utc)
    seconds = int((airing_at - now).total_seconds())
    if seconds <= 0:
        return f"Episode {airing.episode} has aired"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        when = f"{days}d {hours}h"
    elif hours:
        when = f"{hours}h {minutes}m"
    else:
        when = f"{minutes}m"
    return f"Episode {airing.episode} airs in {when}"


def season_text(item: MediaItem) -> Optional[str]:
    if item.start_date is None:
        return None
    month = item.start_date.month
    season = ("Winter", "Spring", "Summer", "Fall")[(month % 12) // 3]
    # AniList counts December as the next year's winter season.
    year = item.start_date.year + (1 if month == 12 else 0)
    return f"{season} {year}"


def strip_html(text: Optional[str]) -> str:
    """Converts AniList's HTML descriptions into plain text."""
    if not text:
        return ""
    text = _BREAK_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text).replace("\r", "")
    return _BLANK_LINES_RE.sub("\n\n", text).strip()
