"""Home tiles and the page loaders behind them.

A loader takes a 1-based page number and returns one page of media. Loaders
only call the existing services, so the TUI stays a presentation layer.
"""

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from ...libs.media_api.params import MediaSearchParams
from ...libs.media_api.types import (
    MediaItem,
    MediaSearchResult,
    MediaSort,
    MediaStatus,
    PageInfo,
    UserListItem,
    UserMediaListStatus,
)

if TYPE_CHECKING:
    from ..interactive.session import Context

Loader = Callable[[int], Optional[MediaSearchResult]]


@dataclass(frozen=True)
class MenuEntry:
    key: str
    icon: str
    title: str
    description: str


HOME_ENTRIES: List[MenuEntry] = [
    MenuEntry("continue", "▶", "Continue Watching", "Pick up where you left off"),
    MenuEntry("library", "▤", "My Library", "Watching, planned, completed…"),
    MenuEntry("search", "⌕", "Search", "Find any anime by title"),
    MenuEntry("trending", "↗", "Trending", "What everyone is watching now"),
    MenuEntry("popular", "✦", "Popular", "All-time most popular"),
    MenuEntry("top", "★", "Top Scored", "Highest rated on AniList"),
    MenuEntry("updated", "↻", "Recently Updated", "Freshly updated entries"),
    MenuEntry("upcoming", "◷", "Upcoming", "Not yet released"),
    MenuEntry("favourites", "❤", "Most Favourited", "Fan favourites"),
    MenuEntry("recent", "◴", "Recently Watched", "From your local history"),
    MenuEntry("random", "⚄", "Random", "Feeling lucky?"),
    MenuEntry("trackers", "⇄", "Trackers", "AniList & MyAnimeList sync"),
    MenuEntry("classic", "☰", "Classic Menu", "The original fzf/rofi menus"),
    MenuEntry("quit", "✕", "Quit", "Leave neoviu"),
]

SORTED_TILES = {
    "trending": (MediaSort.TRENDING_DESC, None),
    "popular": (MediaSort.POPULARITY_DESC, None),
    "top": (MediaSort.SCORE_DESC, None),
    "updated": (MediaSort.UPDATED_AT_DESC, None),
    "upcoming": (MediaSort.POPULARITY_DESC, MediaStatus.NOT_YET_RELEASED),
    "favourites": (MediaSort.FAVOURITES_DESC, None),
}


def page_size(ctx: "Context") -> int:
    return ctx.config.anilist.per_page or 15


def search_loader(
    ctx: "Context",
    *,
    query: Optional[str] = None,
    sort: Optional[MediaSort] = None,
    status: Optional[MediaStatus] = None,
    id_in: Optional[List[int]] = None,
) -> Loader:
    per_page = page_size(ctx)

    def load(page: int) -> Optional[MediaSearchResult]:
        return ctx.media_api.search_media(
            MediaSearchParams(
                query=query,
                sort=sort,
                status=status,
                id_in=id_in,
                page=page,
                per_page=per_page,
            )
        )

    return load


def sorted_loader(ctx: "Context", key: str) -> Loader:
    sort, status = SORTED_TILES[key]
    return search_loader(ctx, sort=sort, status=status)


def random_loader(ctx: "Context") -> Loader:
    ids = random.sample(range(1, 15000), k=50)
    return search_loader(ctx, id_in=ids, sort=MediaSort.POPULARITY_DESC)


def user_list_loader(ctx: "Context", status: UserMediaListStatus) -> Loader:
    per_page = page_size(ctx)

    def load(page: int) -> Optional[MediaSearchResult]:
        return ctx.tracking.get_user_list(status, page=page, per_page=per_page)

    return load


def recent_loader(ctx: "Context") -> Loader:
    """Locally watched anime, newest first, with local progress as the badge."""
    per_page = page_size(ctx)

    def load(page: int) -> Optional[MediaSearchResult]:
        registry = ctx.media_registry
        media = [
            with_local_status(item, registry)
            for item in registry.get_recently_watched().media
        ]
        return paginate(media, page, per_page)

    return load


def continue_loader(ctx: "Context") -> Loader:
    """The tracker's Watching list, or local history when nothing is tracked."""
    tracked = user_list_loader(ctx, UserMediaListStatus.WATCHING)
    local = recent_loader(ctx)

    def load(page: int) -> Optional[MediaSearchResult]:
        if ctx.tracking.can_track:
            return tracked(page)
        return local(page)

    return load


def with_local_status(item: MediaItem, registry) -> MediaItem:
    if item.user_status is not None:
        return item
    entry = registry.get_media_index_entry(item.id)
    if entry is None:
        return item
    try:
        progress = int(float(entry.progress))
    except (TypeError, ValueError):
        progress = 0
    return item.model_copy(
        update={
            "user_status": UserListItem(
                status=entry.status, progress=progress, score=entry.score or None
            )
        }
    )


def paginate(media: List[MediaItem], page: int, per_page: int) -> MediaSearchResult:
    start = (page - 1) * per_page
    return MediaSearchResult(
        page_info=PageInfo(
            total=len(media),
            current_page=page,
            has_next_page=start + per_page < len(media),
            per_page=per_page,
        ),
        media=media[start : start + per_page],
    )


def refresh_item(ctx: "Context", item: MediaItem) -> MediaItem:
    """Re-fetches an item from the metadata API, falling back to the old copy."""
    result = ctx.media_api.search_media(MediaSearchParams(id_in=[item.id], per_page=1))
    if result and result.media:
        return result.media[0]
    return item


def load_item_state(
    ctx: "Context", item: MediaItem
) -> Tuple[MediaItem, Dict[str, Optional[UserListItem]]]:
    """Fetches an item and its entry on every tracker.

    The returned item carries the entry of the list source (AniList first,
    then MyAnimeList, then local history), so badges match the Library.
    """
    fresh = refresh_item(ctx, item)
    tracking = ctx.tracking
    entries = tracking.list_entries(fresh)
    source = tracking.list_source
    if source is not None:
        fresh = fresh.model_copy(update={"user_status": entries.get(source)})
    else:
        fresh = with_local_status(
            fresh.model_copy(update={"user_status": None}), ctx.media_registry
        )
    return fresh, entries
