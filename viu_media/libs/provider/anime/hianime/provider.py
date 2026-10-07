import logging
import re
from collections.abc import Iterator

from httpx import Client, HTTPError, Response

from .....core.exceptions import (
    NoStreamsFoundError,
    ProviderAPIError,
    ProviderError,
    ProviderParsingError,
)
from ..base import BaseAnimeProvider
from ..extractors import extract_server
from ..params import AnimeParams, EpisodeStreamsParams, SearchParams
from ..types import Anime, AnimeEpisodes, SearchResult, SearchResults, Server
from ..utils.debug import debug_provider
from .constants import AJAX_HEADERS, EMBED_SERVERS, HIANIME_BASE, REQUEST_HEADERS
from .mappers import map_embeds, map_episodes, map_search_results

logger = logging.getLogger(__name__)


def _ajax_html(response: Response) -> str:
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("html"), str):
        raise ProviderParsingError("hianime", "Invalid episode API response.")
    if data.get("status") is False:
        raise ProviderAPIError(
            "hianime", details="The episode API rejected the request."
        )
    return data["html"]


class HiAnime(BaseAnimeProvider):
    HEADERS = REQUEST_HEADERS

    def __init__(self, client: Client) -> None:
        super().__init__(client)
        self._results: dict[str, SearchResult] = {}
        self._anime: dict[str, Anime] = {}

    @debug_provider
    def search(self, params: SearchParams) -> SearchResults:
        response = self.client.get(
            f"{HIANIME_BASE}/search",
            params={"keyword": params.query, "page": params.current_page},
            follow_redirects=True,
        )
        response.raise_for_status()
        if re.search(
            r"<title[^>]*>\s*(?:Just a moment|Attention Required)",
            response.text,
            re.IGNORECASE,
        ):
            raise ProviderAPIError(
                "hianime", details="The site requires browser verification."
            )
        results = map_search_results(response.text, params)
        self._results.update({result.id: result for result in results.results})
        return results

    @debug_provider
    def get(self, params: AnimeParams) -> Anime:
        if not re.fullmatch(r"[^/?#]+-\d+", params.id):
            raise ProviderParsingError("hianime", "Invalid anime identifier.")
        if params.id not in self._results:
            self.search(SearchParams(query=params.query))
        result = self._results.get(params.id)
        if result is None:
            raise ProviderParsingError("hianime", "The requested anime was not found.")
        response = self.client.get(
            f"{HIANIME_BASE}/api/theme/episode/list/{params.id.rsplit('-', 1)[-1]}",
            headers=AJAX_HEADERS,
            follow_redirects=True,
        )
        episodes = map_episodes(_ajax_html(response), params.id)
        numbers = [episode.episode for episode in episodes]
        anime = Anime(
            id=params.id,
            title=result.title,
            episodes=AnimeEpisodes(sub=numbers, dub=numbers),
            episodes_info=episodes,
        )
        self._anime[params.id] = anime
        return anime

    @debug_provider
    def episode_streams(self, params: EpisodeStreamsParams) -> Iterator[Server]:
        anime = self._anime.get(params.anime_id)
        episodes = anime.episodes_info if anime else None
        episode = next(
            (
                item
                for item in episodes or []
                if float(item.episode) == float(params.episode)
            ),
            None,
        )
        if episode is None:
            anime = self.get(AnimeParams(id=params.anime_id, query=params.query))
            episode = next(
                (
                    item
                    for item in anime.episodes_info or []
                    if float(item.episode) == float(params.episode)
                ),
                None,
            )
        if episode is None:
            raise NoStreamsFoundError("hianime", params.query, params.episode)
        response = self.client.get(
            f"{HIANIME_BASE}/api/theme/episode/servers",
            params={"episodeId": episode.id},
            headers=AJAX_HEADERS,
            follow_redirects=True,
        )
        embeds = map_embeds(_ajax_html(response), params.translation_type)
        preferred = params.server.casefold() if params.server else None
        if preferred in EMBED_SERVERS:
            preferred = EMBED_SERVERS[preferred].value
        found = False
        last_error: Exception | None = None
        for name, url in embeds:
            if preferred not in (None, "top", name.value):
                continue
            try:
                server = extract_server(
                    self.client, name, url, params, provider_name="hianime"
                )
            except (HTTPError, ProviderError, ValueError) as error:
                logger.warning(
                    "HiAnime %s failed (%s); trying another host.",
                    name.value,
                    type(error).__name__,
                )
                last_error = error
                continue
            found = True
            yield server
        if not found:
            if last_error is not None:
                raise ProviderParsingError(
                    "hianime", "All available streaming hosts failed to resolve."
                ) from last_error
            raise NoStreamsFoundError("hianime", params.query, params.episode)
