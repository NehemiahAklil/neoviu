import json
import re
from base64 import b64encode, urlsafe_b64encode
from urllib.parse import parse_qs

import pytest
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad
from pytest_httpx import HTTPXMock

from viu_media.core.exceptions import NoStreamsFoundError, ProviderAPIError
from viu_media.libs.provider.anime.params import (
    AnimeParams,
    EpisodeStreamsParams,
    SearchParams,
)
from viu_media.libs.provider.anime.provider import create_provider
from viu_media.libs.provider.anime.types import ProviderName

BASE = "https://hianime.at"
ZOKO = "https://zokoanime.video/stream/mal/20/1/sub"
MEGAPLAY = "https://megaplay.buzz/stream/s-2/123/sub?s=tcdn"
MASTER = "https://video.example/hls/master.m3u8"
PLAYLIST = """#EXTM3U
#EXT-X-I-FRAME-STREAM-INF:RESOLUTION=1920x1080,URI="trickplay.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1280x800
high/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=500000,RESOLUTION=640x360
https://video.example/low/index.m3u8
"""


def add_catalogue(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=re.compile(re.escape(BASE + "/search")),
        text="""
        <div class="film-detail"><h3 class="film-name">
          <a href="/naruto-123" title="Naruto">Naruto</a>
        </h3></div>
        <div id="main-sidebar"><div class="film-detail"><h3 class="film-name">
          <a href="/unrelated-999" title="Unrelated">Unrelated</a>
        </h3></div></div>
        """,
    )
    httpx_mock.add_response(
        url=BASE + "/api/theme/episode/list/123",
        json={
            "status": True,
            "totalItems": 1,
            "html": """
            <a class="ep-item" data-number="1" data-id="999"
               href="/watch/other-999?ep=999">Wrong show</a>
            <a class="ep-item" data-number="1" data-id="41" title="Episode 1"
               href="/watch/naruto-123?ep=41">1</a>
            <a class="ep-item" data-number="2" data-id="42" title="Episode 2"
               href="/watch/naruto-123?ep=42">2</a>
            """,
        },
    )


def server_html(name: str, url: str, mode: str = "sub") -> str:
    encoded = b64encode(url.encode()).decode()
    return (
        f'<div class="item server-item" data-hash="{encoded}" '
        f'data-server-name="{name}" data-type="{mode}"></div>'
    )


def add_zoko(httpx_mock: HTTPXMock) -> None:
    key = b"otaku-embed-v1"
    payload = json.dumps(
        {
            "src": MASTER,
            "subtitles": [
                {"lang": "en", "src": "https://subs.example/en.vtt", "default": True}
            ],
        }
    ).encode()
    encoded = b64encode(
        bytes(value ^ key[index % len(key)] for index, value in enumerate(payload))
    ).decode()
    httpx_mock.add_response(
        url=ZOKO, text=f'<script>window.__P = "{encoded}";</script>'
    )
    httpx_mock.add_response(url=MASTER, text=PLAYLIST)


def test_hianime_search_details_and_zoko_stream_pipeline(httpx_mock: HTTPXMock) -> None:
    add_catalogue(httpx_mock)
    httpx_mock.add_response(
        url=BASE + "/api/theme/episode/servers?episodeId=41",
        json={"status": True, "html": server_html("ZokoAnime", ZOKO)},
    )
    add_zoko(httpx_mock)
    provider = create_provider(ProviderName.HIANIME)
    try:
        search = provider.search(SearchParams(query="Naruto"))
        assert search and [result.title for result in search.results] == ["Naruto"]
        anime = provider.get(AnimeParams(id="naruto-123", query="Naruto"))
        assert anime and anime.episodes.sub == ["1", "2"]
        assert anime.episodes_info and anime.episodes_info[0].id == "41"
        streams = provider.episode_streams(
            EpisodeStreamsParams(query="Naruto", anime_id=anime.id, episode="1")
        )
        assert streams is not None
        servers = list(streams)
    finally:
        provider.client.close()
    assert len(servers) == 1
    assert servers[0].name == "zokoanime"
    assert [link.quality for link in servers[0].links] == ["800", "360"]
    assert servers[0].links[0].link == "https://video.example/hls/high/index.m3u8"
    assert servers[0].headers["Referer"] == "https://zokoanime.video/"
    assert servers[0].subtitles[0].url == "https://subs.example/en.vtt"
    manifest_request = next(
        request for request in httpx_mock.get_requests() if str(request.url) == MASTER
    )
    assert manifest_request.headers["Referer"] == "https://zokoanime.video/"


def test_hianime_falls_back_to_curd_compatible_megaplay(httpx_mock: HTTPXMock) -> None:
    add_catalogue(httpx_mock)
    httpx_mock.add_response(
        url=BASE + "/api/theme/episode/servers?episodeId=41",
        json={
            "status": True,
            "html": server_html("ZokoAnime", ZOKO) + server_html("HD-1", MEGAPLAY),
        },
    )
    httpx_mock.add_response(url=ZOKO, status_code=503)
    httpx_mock.add_response(url=MEGAPLAY, text='<div data-id="55"></div>')
    cipher = AES.new(
        b"i?LMTAx0Q6,:}50U".ljust(32, b"\x00"),
        AES.MODE_CBC,
        iv=b"W0;27ToaUpl_P%'c",
    )
    encrypted = cipher.encrypt(
        pad(json.dumps({"file": MASTER}).encode(), AES.block_size)
    )
    httpx_mock.add_response(
        url="https://megaplay.buzz/stream/getSources?id=55",
        json={
            "enc": urlsafe_b64encode(encrypted).decode().rstrip("="),
            "tracks": [
                {
                    "kind": "captions",
                    "label": "English",
                    "file": "https://subs.example/en.vtt",
                }
            ],
        },
    )
    httpx_mock.add_response(url=MASTER, text=PLAYLIST)
    provider = create_provider(ProviderName.HIANIME)
    try:
        streams = provider.episode_streams(
            EpisodeStreamsParams(
                query="Naruto", anime_id="naruto-123", episode="1", subtitles=False
            )
        )
        assert streams is not None
        servers = list(streams)
    finally:
        provider.client.close()
    assert [server.name for server in servers] == ["megaplay"]
    assert servers[0].links[0].quality == "800"
    assert servers[0].subtitles == []
    assert servers[0].headers["Referer"] == "https://megaplay.buzz/"


def test_hianime_does_not_use_sub_servers_for_a_dub_request(
    httpx_mock: HTTPXMock,
) -> None:
    add_catalogue(httpx_mock)
    httpx_mock.add_response(
        url=BASE + "/api/theme/episode/servers?episodeId=41",
        json={"status": True, "html": server_html("ZokoAnime", ZOKO, mode="sub")},
    )
    provider = create_provider(ProviderName.HIANIME)
    try:
        streams = provider.episode_streams(
            EpisodeStreamsParams(
                query="Naruto",
                anime_id="naruto-123",
                episode="1",
                translation_type="dub",
            )
        )
        assert streams is not None
        with pytest.raises(NoStreamsFoundError):
            list(streams)
    finally:
        provider.client.close()


def test_hianime_empty_search_ignores_sidebar_recommendations(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url=re.compile(re.escape(BASE + "/search")),
        text="""
        <main>No results</main><aside id="main-sidebar">
          <div class="film-detail"><h3 class="film-name">
            <a href="/naruto-123" title="Naruto">Naruto</a>
          </h3></div>
        </aside>
        """,
    )
    provider = create_provider(ProviderName.HIANIME)
    try:
        results = provider.search(SearchParams(query="missing", current_page=2))
    finally:
        provider.client.close()
    assert results and results.results == []
    request = httpx_mock.get_request()
    assert request is not None
    assert parse_qs(request.url.query.decode())["page"] == ["2"]


def test_hianime_browser_challenge_is_not_an_empty_result(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url=re.compile(re.escape(BASE + "/search")),
        text="<html><title>Just a moment...</title></html>",
    )
    provider = create_provider(ProviderName.HIANIME)
    try:
        with pytest.raises(ProviderAPIError, match="browser verification"):
            provider.search(SearchParams(query="Naruto"))
    finally:
        provider.client.close()
