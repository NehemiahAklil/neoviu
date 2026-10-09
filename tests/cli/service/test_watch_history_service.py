"""Watch history status/progress rules and remote syncing."""

from typing import Optional
from unittest.mock import MagicMock

import pytest

from viu_media.cli.service.watch_history.service import WatchHistoryService
from viu_media.core.config import AppConfig
from viu_media.libs.media_api.types import (
    MediaItem,
    MediaTitle,
    UserListItem,
    UserMediaListStatus,
)
from viu_media.libs.player.types import PlayerResult

S = UserMediaListStatus


def make_item(
    status: Optional[UserMediaListStatus] = None,
    progress: int = 0,
    episodes: Optional[int] = 12,
) -> MediaItem:
    return MediaItem(
        id=1,
        id_mal=101,
        title=MediaTitle(english="Anime"),
        episodes=episodes,
        user_status=UserListItem(status=status, progress=progress) if status else None,
    )


@pytest.fixture
def tracking():
    mock = MagicMock()
    mock.update.return_value = {"anilist": True}
    return mock


@pytest.fixture
def history(tracking):
    return WatchHistoryService(AppConfig(), MagicMock(), tracking=tracking)


@pytest.mark.parametrize(
    "status, episode, finished, expected",
    [
        (S.WATCHING, "12", True, S.COMPLETED),
        (S.WATCHING, "12", False, None),
        (S.WATCHING, "5", True, None),
        (S.PLANNING, "1", True, S.WATCHING),
        (S.PAUSED, "4", True, S.WATCHING),
        (S.DROPPED, "4", False, S.WATCHING),
        (S.COMPLETED, "1", True, S.REPEATING),
        (None, "1", True, None),
    ],
)
def test_status_after_watching(status, episode, finished, expected):
    item = make_item(status, progress=3)
    assert WatchHistoryService._status_after_watching(item, episode, finished) == (
        expected
    )


@pytest.mark.parametrize(
    "status, progress, delta, expected_progress, expected_status",
    [
        (S.PLANNING, 0, 1, 1, S.WATCHING),
        (None, 0, 1, 1, S.WATCHING),
        (S.WATCHING, 11, 1, 12, S.COMPLETED),
        (S.WATCHING, 12, 1, 12, S.COMPLETED),
        (S.COMPLETED, 12, -1, 11, S.WATCHING),
        (S.WATCHING, 0, -1, 0, None),
        (S.WATCHING, 4, 1, 5, None),
    ],
)
def test_step_progress(
    history, tracking, status, progress, delta, expected_progress, expected_status
):
    item = make_item(status, progress)

    new_progress, new_status, results = history.step_progress(item, delta)

    assert (new_progress, new_status) == (expected_progress, expected_status)
    assert results == {"anilist": True}
    tracking.update.assert_called_once_with(
        item, status=expected_status, progress=str(expected_progress), score=None
    )
    history.media_registry.update_media_index_entry.assert_called_once()


def test_step_progress_without_an_episode_count_is_not_capped(history):
    progress, _, _ = history.step_progress(make_item(S.WATCHING, 30, None), 1)
    assert progress == 31


def test_finishing_an_unlisted_episode_starts_tracking_it(history, tracking):
    item = make_item(None)
    history.track(item, PlayerResult(episode="1", stop_time=None, total_time=None))

    tracking.add_if_missing.assert_called_once_with(item, S.WATCHING)
    tracking.update.assert_called_once_with(item, status=None, progress="1", score=None)


def test_an_unfinished_episode_is_only_saved_locally(history, tracking):
    item = make_item(S.WATCHING, 2)
    history.track(
        item, PlayerResult(episode="3", stop_time="00:02:00", total_time="00:24:00")
    )

    history.media_registry.update_media_index_entry.assert_called_once()
    tracking.update.assert_not_called()
    tracking.add_if_missing.assert_not_called()


def test_adding_to_planning_uses_the_trackers(history, tracking):
    tracking.add_if_missing.return_value = ["anilist"]
    item = make_item(None)

    history.add_media_to_list_if_not_present(item)

    tracking.add_if_missing.assert_called_once_with(item)
    kwargs = history.media_registry.update_media_index_entry.call_args.kwargs
    assert kwargs["status"] == S.PLANNING
