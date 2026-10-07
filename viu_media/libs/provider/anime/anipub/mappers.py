import re
from urllib.parse import parse_qs, urljoin, urlsplit

from .....core.exceptions import ProviderParsingError
from ..types import Anime, AnimeEpisodeInfo, AnimeEpisodes, SearchResult
from .constants import ANIPUB_BASE
from .types import AniPubDetails, AniPubInfo, AniPubRecord


def map_search_result(record: AniPubRecord) -> SearchResult:
    return SearchResult(
        id=str(record.id),
        title=record.title,
        poster=urljoin(ANIPUB_BASE, record.image) if record.image else None,
        episodes=AnimeEpisodes(sub=[], dub=[]),
    )


def _embed_id(link: str) -> str:
    url = urlsplit(link.strip().removeprefix("src=").strip().strip("\"'"))
    native = re.fullmatch(r"/video/([1-9][0-9]*)/(sub|dub)/?", url.path)
    if native and url.hostname in (None, "anipub.xyz", "www.anipub.xyz"):
        return native.group(1)
    if url.hostname == "gogoanime.com.by" and url.path == "/streaming.php":
        query = parse_qs(url.query)
        episode_ids = query.get("ep", [])
        modes = query.get("type", [])
        if (
            len(episode_ids) == 1
            and re.fullmatch(r"[1-9][0-9]*", episode_ids[0])
            and len(modes) == 1
            and modes[0] in {"sub", "dub"}
        ):
            return episode_ids[0]
    raise ProviderParsingError(
        "anipub", "The catalogue returned an unsupported episode link."
    )


def map_anime(info: AniPubInfo, details: AniPubDetails) -> Anime:
    episodes = []
    # Episode 1 is separate; epCount counts only the remaining episode links.
    links = [details.local.link, *(episode.link for episode in details.local.ep)]
    for number, link in enumerate(links, start=1):
        if link:
            episodes.append(
                AnimeEpisodeInfo(
                    id=_embed_id(link),
                    episode=str(number),
                    title=f"{info.title} - Episode {number}",
                )
            )
    numbers = [episode.episode for episode in episodes]
    return Anime(
        id=str(info.id),
        title=info.title,
        poster=urljoin(ANIPUB_BASE, info.image) if info.image else None,
        episodes=AnimeEpisodes(sub=numbers, dub=numbers),
        episodes_info=episodes,
    )
