import logging
import re
from base64 import b64decode
from urllib.parse import parse_qs, urlsplit

from ...scraping.html_parser import (
    extract_attributes,
    get_element_by_class,
    get_element_text_and_html_by_tag,
    get_elements_by_tag,
    get_elements_html_by_class,
)
from ..params import SearchParams
from ..types import (
    AnimeEpisodeInfo,
    AnimeEpisodes,
    PageInfo,
    ProviderServer,
    SearchResult,
    SearchResults,
)
from .constants import EMBED_SERVERS

logger = logging.getLogger(__name__)


def map_search_results(html: str, params: SearchParams) -> SearchResults:
    sidebar = re.search(r"""<[^>]+\bid\s*=\s*(['"])main-sidebar\1""", html)
    if sidebar:
        html = html[: sidebar.start()]
    results: dict[str, SearchResult] = {}
    for detail in get_elements_html_by_class("film-detail", html):
        heading = get_element_by_class("film-name", detail)
        if not heading:
            continue
        for anchor in get_elements_by_tag("a", heading):
            attrs = extract_attributes(anchor)
            path = urlsplit(attrs.get("href", "")).path.rstrip("/")
            parts = path.strip("/").split("/")
            if len(parts) == 1:
                anime_id = parts[0]
            elif len(parts) == 2 and parts[0] == "watch":
                anime_id = parts[1]
            else:
                continue
            if not re.fullmatch(r"[^/?#]+-\d+", anime_id):
                continue
            title = (
                attrs.get("title") or get_element_text_and_html_by_tag("a", anchor)[0]
            )
            if not title:
                continue
            other_title = attrs.get("data-jname")
            results[anime_id] = SearchResult(
                id=anime_id,
                title=title.strip(),
                episodes=AnimeEpisodes(sub=[], dub=[]),
                other_titles=[other_title]
                if other_title and other_title != title
                else [],
            )
    return SearchResults(
        page_info=PageInfo(current_page=params.current_page, per_page=len(results)),
        results=list(results.values())[: params.page_limit],
    )


def map_episodes(html: str, anime_id: str) -> list[AnimeEpisodeInfo]:
    episodes: dict[str, AnimeEpisodeInfo] = {}
    for element in get_elements_html_by_class("ep-item", html):
        attrs = extract_attributes(element)
        number = attrs.get("data-number", "")
        episode_id = attrs.get("data-id", "")
        watch_url = urlsplit(attrs.get("href", ""))
        if (
            watch_url.path.rstrip("/") != f"/watch/{anime_id}"
            or not re.fullmatch(r"\d+(?:\.\d+)?", number)
            or not episode_id.isdigit()
            or parse_qs(watch_url.query).get("ep") != [episode_id]
        ):
            continue
        episodes[number] = AnimeEpisodeInfo(
            id=episode_id,
            episode=number,
            title=attrs.get("title"),
        )
    return sorted(episodes.values(), key=lambda episode: float(episode.episode))


def map_embeds(html: str, translation_type: str) -> list[tuple[ProviderServer, str]]:
    embeds: dict[ProviderServer, str] = {}
    for element in get_elements_html_by_class("server-item", html):
        attrs = extract_attributes(element)
        if attrs.get("data-type") != translation_type:
            continue
        name = EMBED_SERVERS.get(attrs.get("data-server-name", "").casefold())
        encoded = attrs.get("data-hash")
        if name is None or not encoded or name in embeds:
            continue
        try:
            url = b64decode(encoded + "=" * (-len(encoded) % 4), validate=True).decode()
        except ValueError:
            logger.warning(
                "HiAnime returned an invalid embed identifier for %s.", name.value
            )
            continue
        embeds[name] = url
    return [
        (name, embeds[name])
        for name in (ProviderServer.ZOKOANIME, ProviderServer.MEGAPLAY)
        if name in embeds
    ]
