"""Pure helpers behind the grid TUI: labels, paging and local list status."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from viu_media.cli.tui import catalog, formatting
from viu_media.libs.media_api.types import (
    AiringSchedule,
    MediaFormat,
    MediaItem,
    MediaStatus,
    MediaTitle,
    UserListItem,
    UserMediaListStatus,
)

S = UserMediaListStatus


def make_item(
    list_status: Optional[UserMediaListStatus] = None,
    progress: int = 0,
    **fields,
) -> MediaItem:
    data: Dict[str, Any] = {
        "id": 1,
        "title": MediaTitle(english="Frieren", romaji="Sousou no Frieren"),
        "episodes": 28,
    }
    data.update(fields)
    if list_status:
        data["user_status"] = UserListItem(status=list_status, progress=progress)
    return MediaItem(**data)


def test_titles():
    item = make_item()
    assert formatting.display_title(item) == "Frieren"
    assert formatting.alt_title(item) == "Sousou no Frieren"
    same = make_item(title=MediaTitle(english="Bleach", romaji="Bleach"))
    assert formatting.alt_title(same) is None


def test_meta_line():
    item = make_item(format=MediaFormat.TV, average_score=91)
    assert formatting.meta_line(item) == "TV · 28 ep · ★ 9.1"
    airing = make_item(
        format=MediaFormat.TV_SHORT, episodes=None, status=MediaStatus.RELEASING
    )
    assert formatting.meta_line(airing) == "Tv Short · Airing"


@pytest.mark.parametrize(
    "status, progress, expected",
    [
        (S.WATCHING, 5, "Watching 5/28"),
        (S.REPEATING, 2, "Rewatching 2/28"),
        (S.PLANNING, 0, "Planning"),
        (S.COMPLETED, 28, "Completed"),
        (None, 0, None),
    ],
)
def test_badge(status, progress, expected):
    assert formatting.badge(make_item(status, progress)) == expected


@pytest.mark.parametrize(
    "status, progress, episodes, expected",
    [
        (None, 0, 28, 1),
        (S.WATCHING, 5, 28, 6),
        (S.WATCHING, 28, 28, 28),
        (S.COMPLETED, 28, 28, 1),
        (S.WATCHING, 40, None, 41),
    ],
)
def test_next_episode(status, progress, episodes, expected):
    item = make_item(status, progress, episodes=episodes)
    assert formatting.next_episode(item) == expected


def test_new_episodes_only_counts_followed_airing_shows():
    airing = dict(status=MediaStatus.RELEASING, next_airing=AiringSchedule(episode=8))
    assert formatting.new_episodes(make_item(S.WATCHING, 4, **airing)) == 3
    assert formatting.new_episodes(make_item(S.PLANNING, 0, **airing)) == 0
    assert formatting.new_episodes(make_item(S.WATCHING, 4)) == 0


def test_airing_text():
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def at(delta: timedelta):
        schedule = AiringSchedule(episode=5, airing_at=now + delta)
        return formatting.airing_text(make_item(next_airing=schedule), now)

    assert at(timedelta(days=2, hours=3)) == "Episode 5 airs in 2d 3h"
    assert at(timedelta(hours=4, minutes=30)) == "Episode 5 airs in 4h 30m"
    assert at(timedelta(minutes=12)) == "Episode 5 airs in 12m"
    assert at(timedelta(minutes=-1)) == "Episode 5 has aired"
    assert formatting.airing_text(make_item()) is None


@pytest.mark.parametrize(
    "month, year, expected",
    [(1, 2024, "Winter 2024"), (4, 2024, "Spring 2024"), (12, 2024, "Winter 2025")],
)
def test_season_text(month, year, expected):
    item = make_item(start_date=datetime(year, month, 1))
    assert formatting.season_text(item) == expected


def test_strip_html():
    text = "<b>Bold</b> &amp; more.<br><br><br><br>Next<br/>line"
    assert formatting.strip_html(text) == "Bold & more.\n\nNext\nline"
    assert formatting.strip_html(None) == ""


def test_paginate():
    items = [make_item(id=i) for i in range(1, 8)]
    page = catalog.paginate(items, page=2, per_page=3)
    assert [m.id for m in page.media] == [4, 5, 6]
    assert page.page_info.has_next_page and page.page_info.total == 7
    assert not catalog.paginate(items, page=3, per_page=3).page_info.has_next_page


def test_with_local_status_fills_in_from_the_registry():
    registry = MagicMock()
    registry.get_media_index_entry.return_value = SimpleNamespace(
        status=S.WATCHING, progress="4", score=0
    )

    item = catalog.with_local_status(make_item(), registry)

    assert item.user_status is not None
    assert (item.user_status.status, item.user_status.progress) == (S.WATCHING, 4)
    assert item.user_status.score is None

    remote = make_item(S.PLANNING)
    assert catalog.with_local_status(remote, registry) is remote
    registry.get_media_index_entry.return_value = None
    assert catalog.with_local_status(make_item(), registry).user_status is None
