import json
import re
from base64 import urlsafe_b64encode

import pytest
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad
from pytest_httpx import HTTPXMock

from viu_media.core.exceptions import (
    NoStreamsFoundError,
    ProviderError,
    ProviderParsingError,
)
from viu_media.libs.provider.anime.params import (
    AnimeParams,
    EpisodeStreamsParams,
    SearchParams,
)
from viu_media.libs.provider.anime.provider import create_provider
from viu_media.libs.provider.anime.types import ProviderName

BASE = "https://anipub.xyz"
MEGAPLAY = "https://megaplay.buzz"
MASTER = "https://video.example/hls/master.m3u8"


def add_anime(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=BASE + "/api/info/82",
        json={"_id": 82, "Name": "Naruto", "ImagePath": "/naruto.jpg", "epCount": 2},
    )
    httpx_mock.add_response(
        url=BASE + "/v1/api/details/82",
        json={
            "local": {
                "link": "src=https://www.anipub.xyz/video/101/sub",
                "ep": [
                    {
                        "link": "src=https://gogoanime.com.by/streaming.php?"
                        "id=naruto-2&ep=102&server=hd-1&type=sub"
                    },
                    {"link": "src=https://www.anipub.xyz/video/103/sub"},
                ],
            }
        },
    )


def add_stream(httpx_mock: HTTPXMock, embed_id: str, translation: str) -> None:
    httpx_mock.add_response(
        url=f"{MEGAPLAY}/stream/s-2/{embed_id}/{translation}",
        match_headers={"Referer": BASE + "/"},
        text='<div data-id="500"></div>',
    )
    cipher = AES.new(
        b"i?LMTAx0Q6,:}50U".ljust(32, b"\x00"),
        AES.MODE_CBC,
        iv=b"W0;27ToaUpl_P%'c",
    )
    encrypted = cipher.encrypt(
        pad(json.dumps({"file": MASTER}).encode(), AES.block_size)
    )
    httpx_mock.add_response(
        url=MEGAPLAY + "/stream/getSources?id=500",
        match_headers={"Referer": MEGAPLAY + "/"},
        json={
            "enc": urlsafe_b64encode(encrypted).decode().rstrip("="),
            "tracks": [
                {"kind": "captions", "label": "English", "file": "/captions/en.vtt"},
            ],
        },
    )
    httpx_mock.add_response(
        url=MASTER,
        match_headers={"Referer": MEGAPLAY + "/"},
        text=(
            "#EXTM3U\n"
            '#EXT-X-I-FRAME-STREAM-INF:RESOLUTION=1920x1080,URI="trickplay.m3u8"\n'
            "#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1280x800\n"
            "800/index.m3u8\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=500000,RESOLUTION=640x360\n"
            "360/index.m3u8\n"
        ),
    )


def test_search_quotes_queries_and_preserves_numeric_ids(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=BASE + "/api/search/One%20Punch%20Man",
        json=[
            {
                "Id": 8248,
                "Name": "One Punch Man",
                "Image": "/one-punch.jpg",
                "finder": "one-punch-man",
            },
            {
                "Id": "8249",
                "Name": "One Punch Man 2",
                "Image": "",
                "finder": "one-punch-man-2",
            },
        ],
    )
    provider = create_provider(ProviderName("anipub"))
    try:
        search = provider.search(
            SearchParams(query="One Punch Man", current_page=2, page_limit=1)
        )
    finally:
        provider.client.close()
    assert search is not None
    assert [result.id for result in search.results] == ["8249"]
    assert search.page_info.total == 2
    assert search.results[0].episodes.sub == []
    assert len(httpx_mock.get_requests()) == 1


def test_search_handles_the_explicit_no_results_response(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=BASE + "/api/search/missing", json={"found": False})
    provider = create_provider(ProviderName("anipub"))
    try:
        search = provider.search(SearchParams(query="missing"))
    finally:
        provider.client.close()
    assert search is not None and search.results == []


def test_details_include_the_separately_stored_first_episode(
    httpx_mock: HTTPXMock,
) -> None:
    add_anime(httpx_mock)
    provider = create_provider(ProviderName("anipub"))
    try:
        anime = provider.get(AnimeParams(id="82", query="Naruto"))
    finally:
        provider.client.close()
    assert anime is not None
    assert anime.id == "82" and anime.title == "Naruto"
    assert anime.poster == BASE + "/naruto.jpg"
    assert anime.episodes.sub == anime.episodes.dub == ["1", "2", "3"]
    assert anime.episodes_info is not None
    assert [episode.id for episode in anime.episodes_info] == ["101", "102", "103"]


@pytest.mark.parametrize(
    ("episode", "embed_id", "translation", "subtitles"),
    [("1", "101", "sub", True), ("2", "102", "dub", False), ("3", "103", "dub", True)],
)
def test_episode_resolution_handles_both_link_formats_and_translations(
    httpx_mock: HTTPXMock,
    episode: str,
    embed_id: str,
    translation: str,
    subtitles: bool,
) -> None:
    add_anime(httpx_mock)
    add_stream(httpx_mock, embed_id, translation)
    provider = create_provider(ProviderName("anipub"))
    try:
        anime = provider.get(AnimeParams(id="82", query="Naruto"))
        assert anime is not None
        streams = provider.episode_streams(
            EpisodeStreamsParams(
                anime_id="82",
                query="Naruto",
                episode=episode,
                translation_type="dub" if translation == "dub" else "sub",
                subtitles=subtitles,
            )
        )
        assert streams is not None
        servers = list(streams)
    finally:
        provider.client.close()
    assert len(servers) == 1 and servers[0].name == "megaplay"
    assert [link.quality for link in servers[0].links] == ["800", "360"]
    assert servers[0].links[0].link == "https://video.example/hls/800/index.m3u8"
    assert servers[0].links[0].translation_type.value == translation
    assert servers[0].headers["Referer"] == MEGAPLAY + "/"
    assert bool(servers[0].subtitles) == subtitles
    if subtitles:
        assert servers[0].subtitles[0].url == MEGAPLAY + "/captions/en.vtt"
    assert len(httpx_mock.get_requests()) == 5


def test_unknown_episode_does_not_generate_a_guessed_embed_request(
    httpx_mock: HTTPXMock,
) -> None:
    add_anime(httpx_mock)
    provider = create_provider(ProviderName("anipub"))
    try:
        streams = provider.episode_streams(
            EpisodeStreamsParams(anime_id="82", query="Naruto", episode="4")
        )
        assert streams is not None
        with pytest.raises(NoStreamsFoundError):
            list(streams)
    finally:
        provider.client.close()
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.parametrize(
    "payload", [{"unexpected": []}, "not a result", [{"Name": "Missing ID"}]]
)
def test_invalid_search_payloads_fail_explicitly(
    httpx_mock: HTTPXMock, payload: object
) -> None:
    httpx_mock.add_response(url=BASE + "/api/search/Naruto", json=payload)
    provider = create_provider(ProviderName("anipub"))
    try:
        with pytest.raises(ProviderParsingError):
            provider.search(SearchParams(query="Naruto"))
    finally:
        provider.client.close()


def test_empty_query_does_not_call_a_nonexistent_api_route() -> None:
    provider = create_provider(ProviderName("anipub"))
    try:
        with pytest.raises(ProviderError):
            provider.search(SearchParams(query=" "))
    finally:
        provider.client.close()


def test_catalogue_rate_limit_is_reported_without_burst_retries(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url=re.compile(re.escape(BASE + "/api/search/")),
        status_code=429,
        headers={"Retry-After": "60"},
    )
    provider = create_provider(ProviderName("anipub"))
    try:
        with pytest.raises(ProviderError, match="429"):
            provider.search(SearchParams(query="Naruto"))
    finally:
        provider.client.close()
    assert len(httpx_mock.get_requests()) == 1


def test_anime_details_do_not_shift_numbering_when_an_episode_is_unavailable(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url=BASE + "/api/info/82",
        json={"_id": 82, "Name": "Naruto", "epCount": 200},
    )
    httpx_mock.add_response(
        url=BASE + "/v1/api/details/82",
        json={
            "local": {
                "link": None,
                "ep": [{"link": "src=/video/102/sub"}, {"link": ""}],
            }
        },
    )
    provider = create_provider(ProviderName("anipub"))
    try:
        anime = provider.get(AnimeParams(id="82", query="Naruto"))
    finally:
        provider.client.close()
    assert anime is not None
    assert anime.episodes.sub == ["2"]
    assert anime.episodes_info is not None and anime.episodes_info[0].id == "102"


def test_slug_ids_are_rejected_before_a_request() -> None:
    provider = create_provider(ProviderName("anipub"))
    try:
        with pytest.raises(ProviderParsingError, match="numeric"):
            provider.get(AnimeParams(id="naruto", query="Naruto"))
    finally:
        provider.client.close()


def test_mismatched_anime_details_are_rejected(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=BASE + "/api/info/82", json={"_id": 38, "Name": "Death Note"}
    )
    provider = create_provider(ProviderName("anipub"))
    try:
        with pytest.raises(ProviderParsingError, match="wrong anime"):
            provider.get(AnimeParams(id="82", query="Naruto"))
    finally:
        provider.client.close()


def test_unrecognized_episode_links_are_not_silently_skipped(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url=BASE + "/api/info/82", json={"_id": 82, "Name": "Naruto"}
    )
    httpx_mock.add_response(
        url=BASE + "/v1/api/details/82",
        json={"local": {"link": "https://unexpected.example/video/123/sub", "ep": []}},
    )
    provider = create_provider(ProviderName("anipub"))
    try:
        with pytest.raises(ProviderParsingError, match="unsupported episode link"):
            provider.get(AnimeParams(id="82", query="Naruto"))
    finally:
        provider.client.close()
