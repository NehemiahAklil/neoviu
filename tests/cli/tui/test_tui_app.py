"""Headless smoke tests for the grid TUI, using fake services (no network)."""

import asyncio
from typing import Dict, List, Optional

import pytest

pytest.importorskip("textual")

from viu_media.cli.interactive.session import Context  # noqa: E402
from viu_media.cli.service.tracking import ANILIST, TRACKER_LABELS, TrackerState  # noqa: E402
from viu_media.cli.service.watch_history.service import WatchHistoryService  # noqa: E402
from viu_media.cli.tui import covers  # noqa: E402
from viu_media.cli.tui.app import ViuApp  # noqa: E402
from viu_media.cli.tui.screens.browse import (  # noqa: E402
    BrowseScreen,
    LibraryScreen,
    SearchScreen,
)
from viu_media.cli.tui.screens.detail import DetailScreen  # noqa: E402
from viu_media.cli.tui.screens.home import HomeScreen  # noqa: E402
from viu_media.cli.tui.screens.trackers import TrackersScreen  # noqa: E402
from viu_media.cli.tui.widgets import MediaBrowser, MediaCard  # noqa: E402
from viu_media.core.config import AppConfig  # noqa: E402
from viu_media.libs.media_api.types import (  # noqa: E402
    MediaItem,
    MediaSearchResult,
    MediaTitle,
    PageInfo,
    UserListItem,
    UserMediaListStatus,
)


def make_item(media_id: int, status: Optional[UserMediaListStatus] = None) -> MediaItem:
    return MediaItem(
        id=media_id,
        id_mal=media_id + 1000,
        title=MediaTitle(english=f"Anime {media_id}", romaji=f"Anime R{media_id}"),
        episodes=12,
        average_score=81,
        description="<b>Great</b> show.<br>Second line.",
        user_status=UserListItem(status=status, progress=3) if status else None,
    )


def make_page(items: List[MediaItem], number: int = 1) -> MediaSearchResult:
    return MediaSearchResult(
        page_info=PageInfo(
            total=len(items), current_page=number, has_next_page=False, per_page=15
        ),
        media=items,
    )


class FakeApi:
    def __init__(self, entries: Dict[int, UserListItem]) -> None:
        self.searches: List[object] = []
        self.entries = entries

    def search_media(self, params):
        self.searches.append(params)
        if params.id_in and len(params.id_in) == 1:
            # Like AniList, a re-fetch carries the user's current list entry.
            media_id = params.id_in[0]
            item = make_item(media_id)
            entry = self.entries.get(media_id)
            return make_page([item.model_copy(update={"user_status": entry})])
        return make_page([make_item(i) for i in range(1, 6)], params.page or 1)

    def is_authenticated(self) -> bool:
        return True


class FakeRegistry:
    def __init__(self) -> None:
        self.updates: List[Dict] = []

    def get_recently_watched(self, limit=None):
        return make_page([])

    def get_media_index_entry(self, media_id):
        return None

    def update_media_index_entry(self, **kwargs) -> None:
        self.updates.append(kwargs)


class FakeTracking:
    def __init__(
        self, config: AppConfig, entries: Dict[int, UserListItem], logged_in: bool
    ) -> None:
        self.config = config
        self.entries = entries
        self.logged_in = logged_in
        self.prompted: set = set()
        self.updates: List[Dict] = []
        self.list_requests: List[UserMediaListStatus] = []
        self.remote = "anilist"
        self.mal_client_id = ""
        self.anilist_login_url = "https://anilist.co/api/v2/oauth/authorize"

    @property
    def enabled_trackers(self) -> List[str]:
        return [ANILIST]

    def is_enabled(self, tracker: str) -> bool:
        return tracker == ANILIST

    def is_logged_in(self, tracker: str) -> bool:
        return self.logged_in and tracker == ANILIST

    def username(self, tracker: str) -> Optional[str]:
        return "tester" if self.logged_in else None

    def states(self) -> List[TrackerState]:
        return [
            TrackerState(
                ANILIST,
                TRACKER_LABELS[ANILIST],
                True,
                self.logged_in,
                self.username(ANILIST),
            )
        ]

    def missing_logins(self) -> List[str]:
        return [] if self.logged_in else [ANILIST]

    @property
    def list_source(self) -> Optional[str]:
        return ANILIST if self.logged_in else None

    @property
    def can_track(self) -> bool:
        return self.logged_in

    def get_user_list(self, status, page=1, per_page=15):
        self.list_requests.append(status)
        items = [make_item(10 + i, status) for i in range(3)]
        for item in items:
            self.entries.setdefault(item.id, item.user_status)  # type: ignore[arg-type]
        return make_page(items)

    def list_entries(self, item: MediaItem):
        return {ANILIST: item.user_status} if self.logged_in else {}

    def update(self, media_item, status=None, progress=None, score=None):
        self.updates.append(
            {
                "id": media_item.id,
                "status": status,
                "progress": progress,
                "score": score,
            }
        )
        entry = self.entries.get(media_item.id) or UserListItem()
        changes = {"status": status, "score": score}
        if progress is not None:
            changes["progress"] = int(progress)
        self.entries[media_item.id] = entry.model_copy(
            update={k: v for k, v in changes.items() if v is not None}
        )
        return {ANILIST: True}

    def delete(self, media_item):
        self.entries.pop(media_item.id, None)
        return {ANILIST: True}


def make_app(logged_in: bool = True):
    config = AppConfig()
    entries: Dict[int, UserListItem] = {}
    api = FakeApi(entries)
    registry = FakeRegistry()
    tracking = FakeTracking(config, entries, logged_in)
    ctx = Context(
        config,
        _media_api=api,  # type: ignore[arg-type]
        _media_registry=registry,  # type: ignore[arg-type]
        _tracking=tracking,  # type: ignore[arg-type]
    )
    ctx._watch_history = WatchHistoryService(config, registry, api, tracking)  # type: ignore[arg-type]
    return ViuApp(config, context=ctx), tracking, api


@pytest.fixture(autouse=True)
def no_images():
    covers.prepare_images(False)


async def settle(pilot) -> None:
    for _ in range(3):
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def test_browse_detail_progress_and_library():
    app, tracking, api = make_app()

    async def run() -> None:
        async with app.run_test(size=(150, 50)) as pilot:
            await settle(pilot)
            assert isinstance(app.screen, HomeScreen)
            assert "tester" in str(app.screen.query_one("#tracker-status").render())

            # The first tile is Continue Watching, backed by the Watching list.
            await pilot.press("enter")
            await settle(pilot)
            assert isinstance(app.screen, BrowseScreen)
            assert tracking.list_requests == [UserMediaListStatus.WATCHING]
            cards = list(app.screen.query(MediaCard))
            assert len(cards) == 3
            assert app.screen.focused is cards[0]

            await pilot.press("enter")
            await settle(pilot)
            assert isinstance(app.screen, DetailScreen)
            await pilot.press("plus")
            await settle(pilot)
            assert tracking.updates[-1]["progress"] == "4"
            entry = app.screen.item.user_status
            assert entry is not None and entry.progress == 4

            await pilot.press("escape")
            await settle(pilot)
            assert isinstance(app.screen, BrowseScreen)
            await pilot.press("escape")
            await settle(pilot)

            await pilot.press("l")
            await settle(pilot)
            assert isinstance(app.screen, LibraryScreen)
            await pilot.press("right_square_bracket")
            await settle(pilot)
            assert tracking.list_requests[-1] == UserMediaListStatus.PLANNING
            await pilot.press("escape")
            await settle(pilot)

            await pilot.press("slash")
            await settle(pilot)
            assert isinstance(app.screen, SearchScreen)
            await pilot.press(*"frieren", "enter")
            await settle(pilot)
            assert getattr(api.searches[-1], "query") == "frieren"
            assert len(app.screen.query_one(MediaBrowser).grid.cards()) == 5

    asyncio.run(run())


def test_status_dialog_updates_tracker():
    app, tracking, _ = make_app()

    async def run() -> None:
        async with app.run_test(size=(150, 50)) as pilot:
            await settle(pilot)
            app.open_media(make_item(42))
            await settle(pilot)
            await pilot.press("s")
            await settle(pilot)
            # Planning is the second option.
            await pilot.press("down", "enter")
            await settle(pilot)
            assert tracking.updates[-1]["status"] == UserMediaListStatus.PLANNING

    asyncio.run(run())


def test_logged_out_user_is_prompted_once():
    app, tracking, _ = make_app(logged_in=False)

    async def run() -> None:
        async with app.run_test(size=(150, 50)) as pilot:
            await settle(pilot)
            assert isinstance(app.screen, TrackersScreen)
            assert app.screen.intro
            await pilot.press("escape")
            await settle(pilot)
            assert isinstance(app.screen, HomeScreen)
            assert "tui" in tracking.prompted

    asyncio.run(run())
