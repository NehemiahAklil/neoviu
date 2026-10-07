from dataclasses import dataclass
from typing import Literal, Optional

from .types import VideoQuality


@dataclass(frozen=True)
class SearchParams:
    """Parameters for searching anime."""

    query: str

    # pagination and sorting
    current_page: int = 1
    page_limit: int = 20
    sort_by: str = "relevance"
    order: Literal["asc", "desc"] = "desc"

    # filters
    translation_type: Literal["sub", "dub"] = "sub"
    genre: Optional[str] = None
    year: Optional[int] = None
    status: Optional[str] = None
    allow_nsfw: bool = True
    allow_unknown: bool = True
    country_of_origin: Optional[str] = None


@dataclass(frozen=True)
class EpisodeStreamsParams:
    """Parameters for fetching episode streams."""

    query: str
    anime_id: str
    episode: str
    translation_type: Literal["sub", "dub"] = "sub"
    server: Optional[str] = None
    quality: VideoQuality = "720"
    subtitles: bool = True


@dataclass(frozen=True)
class AnimeParams:
    """Parameters for fetching anime details."""

    id: str
    # HACK: for the sake of providers which require previous data
    query: str
