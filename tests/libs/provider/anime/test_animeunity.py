from typing import Literal

import httpx
import pytest
from pytest_httpx import HTTPXMock

from viu_media.core.exceptions import ProviderParsingError
from viu_media.libs.provider.anime.animeunity.constants import ANIMEUNITY_BASE
from viu_media.libs.provider.anime.animeunity.extractor import extract_server_info
from viu_media.libs.provider.anime.animeunity.mappers import map_to_server
from viu_media.libs.provider.anime.animeunity.provider import AnimeUnity
from viu_media.libs.provider.anime.params import SearchParams
from viu_media.libs.provider.anime.types import AnimeEpisodeInfo


def test_extract_server_info_reads_javascript_data() -> None:
    info = extract_server_info(
        """
        <script>
        window.video = {id: 1, name: "Naruto", available: true, extra: null};
        window.downloadUrl = 'https://video.example/720p/episode.mp4';
        </script>
        """,
        "Naruto - Ep 1",
    )

    assert info is not None
    assert info["id"] == 1
    assert info["available"] is True
    assert info["extra"] is None
    assert info["quality"] == 720
    assert info["link"] == "https://video.example/720p/episode.mp4"


def test_extract_server_info_does_not_evaluate_expressions() -> None:
    assert (
        extract_server_info(
            """
            <script>
            window.video = {id: 1 + 2};
            window.downloadUrl = 'https://video.example/720p/episode.mp4';
            </script>
            """,
            "Naruto - Ep 1",
        )
        is None
    )


def test_extract_server_info_reads_single_quoted_embed_data() -> None:
    info = extract_server_info(
        r"""
        <script>
        window.video = {
            id: '123',
            filename: 'Naruto: it\'s true, not null.mp4',
            timestamps: [[0, 30,], [1300, 1380]],
        };
        window.downloadUrl = 'https://video.example/1080p/episode.mp4';
        </script>
        """,
        "Naruto - Ep 1",
    )

    assert info is not None
    assert info["id"] == "123"
    assert info["filename"] == "Naruto: it's true, not null.mp4"
    assert info["timestamps"] == [[0, 30], [1300, 1380]]
    assert info["quality"] == 1080


@pytest.mark.parametrize("translation_type", ["sub", "dub"])
def test_search_filters_the_requested_translation(
    httpx_mock: HTTPXMock, translation_type: Literal["sub", "dub"]
) -> None:
    httpx_mock.add_response(
        url=ANIMEUNITY_BASE,
        text='<meta name="csrf-token" content="test-token">',
        headers={"set-cookie": "animeunity_session=test-session; Path=/"},
    )
    httpx_mock.add_response(
        url=f"{ANIMEUNITY_BASE}/livesearch",
        method="POST",
        json={
            "records": [
                {
                    "id": dub + 1,
                    "title_eng": "Naruto",
                    "dub": dub,
                    "episodes_count": 220,
                    "score": 8.0,
                    "imageurl": "https://image.example/naruto.jpg",
                    "date": "2002",
                }
                for dub in [1, 0]
            ]
        },
    )
    with httpx.Client() as client:
        result = AnimeUnity(client).search(
            SearchParams(query="naruto", translation_type=translation_type)
        )
    assert result is not None
    assert len(result.results) == 1
    assert result.results[0].id == ("2" if translation_type == "dub" else "1")
    assert len(getattr(result.results[0].episodes, translation_type)) == 220


def test_sessions_and_search_caches_are_not_shared(httpx_mock: HTTPXMock) -> None:
    for token in ["first-token", "second-token"]:
        httpx_mock.add_response(
            url=ANIMEUNITY_BASE,
            text=f'<meta name="csrf-token" content="{token}">',
            headers={"set-cookie": f"animeunity_session={token}; Path=/"},
        )
    with httpx.Client() as first_client, httpx.Client() as second_client:
        first = AnimeUnity(first_client)
        second = AnimeUnity(second_client)
        first._get_token()
        second._get_token()

        assert first_client.headers["x-csrf-token"] == "first-token"
        assert second_client.headers["x-csrf-token"] == "second-token"
        assert first_client.cookies["animeunity_session"] == "first-token"
        assert second_client.cookies["animeunity_session"] == "second-token"
        assert "x-csrf-token" not in AnimeUnity.HEADERS
        assert first._cache is not second._cache


def test_missing_csrf_token_is_an_explicit_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=ANIMEUNITY_BASE, text="<html>Unavailable</html>")
    with httpx.Client() as client:
        with pytest.raises(ProviderParsingError, match="CSRF"):
            AnimeUnity(client)._get_token()


def test_quality_changes_preserve_signed_url_tokens() -> None:
    server = map_to_server(
        AnimeEpisodeInfo(id="1", episode="1"),
        {
            "link": "https://video.example/1080p/episode-1080.mp4?token=1080-signature",
            "name": "Naruto - Ep 1",
            "quality": 1080,
        },
        "sub",
    )
    assert [link.quality for link in server.links] == ["1080", "720", "480"]
    for link in server.links:
        assert link.link == (
            f"https://video.example/{link.quality}p/"
            "episode-1080.mp4?token=1080-signature"
        )
