import re
from collections.abc import Iterator
from urllib.parse import quote

from httpx import Client
from pydantic import TypeAdapter

from .....core.exceptions import NoStreamsFoundError, ProviderParsingError
from .....core.utils.networking import TIMEOUT
from ..base import BaseAnimeProvider
from ..extractors import extract_server
from ..params import AnimeParams, EpisodeStreamsParams, SearchParams
from ..types import Anime, PageInfo, ProviderServer, SearchResults, Server
from ..utils.debug import debug_provider
from .constants import ANIPUB_BASE, MEGAPLAY_BASE, REQUEST_HEADERS
from .mappers import map_anime, map_search_result
from .types import AniPubDetails, AniPubInfo, AniPubRecord

_search_adapter = TypeAdapter(list[AniPubRecord])


class AniPub(BaseAnimeProvider):
    HEADERS = REQUEST_HEADERS

    def __init__(self, client: Client) -> None:
        super().__init__(client)
        self._anime: dict[str, Anime] = {}

    @debug_provider
    def search(self, params: SearchParams) -> SearchResults:
        query = params.query.strip()
        if not query or params.current_page < 1 or params.page_limit < 1:
            raise ProviderParsingError(
                "anipub", "Search requires a title and positive page settings."
            )
        response = self.client.get(
            f"{ANIPUB_BASE}/api/search/{quote(query, safe='')}",
            follow_redirects=True,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        records = (
            []
            if payload == {"found": False}
            else _search_adapter.validate_python(payload)
        )
        start = (params.current_page - 1) * params.page_limit
        return SearchResults(
            page_info=PageInfo(
                total=len(records),
                current_page=params.current_page,
                per_page=params.page_limit,
            ),
            results=[
                map_search_result(record)
                for record in records[start : start + params.page_limit]
            ],
        )

    @debug_provider
    def get(self, params: AnimeParams) -> Anime:
        if not re.fullmatch(r"[1-9][0-9]*", params.id):
            raise ProviderParsingError(
                "anipub", "A numeric catalogue identifier is required."
            )
        response = self.client.get(
            f"{ANIPUB_BASE}/api/info/{params.id}",
            follow_redirects=True,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        info = AniPubInfo.model_validate(response.json())
        if str(info.id) != params.id:
            raise ProviderParsingError(
                "anipub", "The catalogue returned the wrong anime."
            )
        response = self.client.get(
            f"{ANIPUB_BASE}/v1/api/details/{params.id}",
            follow_redirects=True,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        anime = map_anime(info, AniPubDetails.model_validate(response.json()))
        self._anime[anime.id] = anime
        return anime

    @debug_provider
    def episode_streams(self, params: EpisodeStreamsParams) -> Iterator[Server]:
        if params.server and params.server.casefold() not in {"top", "megaplay"}:
            raise NoStreamsFoundError("anipub", params.query, params.episode)
        anime = self._anime.get(params.anime_id)
        if anime is None:
            anime = self.get(AnimeParams(id=params.anime_id, query=params.query))
        episode = next(
            (
                item
                for item in anime.episodes_info or []
                if item.episode == params.episode
            ),
            None,
        )
        if episode is None:
            raise NoStreamsFoundError("anipub", params.query, params.episode)
        server = extract_server(
            self.client,
            ProviderServer.MEGAPLAY,
            f"{MEGAPLAY_BASE}/stream/s-2/{episode.id}/{params.translation_type}",
            params,
            provider_name="anipub",
            embed_referer=ANIPUB_BASE + "/",
        )
        yield server.model_copy(update={"episode_title": episode.title})
