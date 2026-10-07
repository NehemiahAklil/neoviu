import os
from collections.abc import Generator
from urllib.parse import urlsplit

import httpx
import pytest

from viu_media.libs.provider.anime.params import (
    AnimeParams,
    EpisodeStreamsParams,
    SearchParams,
)
from viu_media.libs.provider.anime.provider import create_provider
from viu_media.libs.provider.anime.types import ProviderName

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("VIU_LIVE_TESTS") != "1",
        reason="Set VIU_LIVE_TESTS=1 to contact live providers and media servers.",
    ),
]


@pytest.mark.parametrize("provider_name", ProviderName)
@pytest.mark.parametrize("title", ["Naruto", "Death Note", "One Punch Man"])
def test_live_search_details_and_first_episode(
    provider_name: ProviderName, title: str
) -> None:
    provider = create_provider(provider_name)
    provider.client.timeout = httpx.Timeout(15)
    try:
        search = provider.search(SearchParams(query=title.lower(), page_limit=40))
        assert search and search.results, f"{provider_name.value}: no search results"
        selected = next(
            (
                result
                for result in search.results
                if result.title.casefold() == title.casefold()
            ),
            None,
        )
        assert selected is not None, f"{provider_name.value}: {title} not found"
        anime = provider.get(AnimeParams(id=selected.id, query=title.lower()))
        assert anime and anime.episodes.sub, f"{provider_name.value}: no episodes"
        assert anime.id == selected.id
        streams = provider.episode_streams(
            EpisodeStreamsParams(
                anime_id=anime.id,
                query=title.lower(),
                episode=min(anime.episodes.sub, key=float),
            )
        )
        assert streams is not None, f"{provider_name.value}: no stream iterator"
        try:
            server = next(streams, None)
        finally:
            if isinstance(streams, Generator):
                streams.close()
        assert server and server.links, f"{provider_name.value}: no playable streams"
        stream_url = server.links[0].link
        assert urlsplit(stream_url).scheme in {"http", "https"}
        with httpx.Client(
            headers=server.headers, follow_redirects=True, timeout=15
        ) as client:
            with client.stream(
                "GET", stream_url, headers={"Range": "bytes=0-127"}
            ) as response:
                response.raise_for_status()
                prefix = next(response.iter_bytes(chunk_size=128), b"")
                assert b"ftyp" in prefix[:32] or prefix.lstrip().startswith(
                    b"#EXTM3U"
                ), f"{provider_name.value}: response is not MP4 or HLS media"
    finally:
        provider.client.close()
