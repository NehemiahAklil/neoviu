import json
import re
from base64 import b64decode
from typing import Any
from urllib.parse import urljoin, urlsplit

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad
from httpx import Client

from ....core.exceptions import ProviderParsingError
from ..scraping.html_parser import extract_attributes, get_elements_by_tag
from .params import EpisodeStreamsParams
from .types import (
    EpisodeStream,
    MediaTranslationType,
    ProviderServer,
    Server,
    Subtitle,
)

EMBED_HOSTS = {
    ProviderServer.ZOKOANIME: "zokoanime.video",
    ProviderServer.MEGAPLAY: "megaplay.buzz",
}

# Public obfuscation constants from the embed players, not account credentials.
ZOKO_KEY = b"otaku-embed-v1"
MEGAPLAY_KEY = b"i?LMTAx0Q6,:}50U".ljust(32, b"\x00")
MEGAPLAY_IV = b"W0;27ToaUpl_P%'c"


def _web_url(value: object, provider_name: str) -> str:
    if not isinstance(value, str):
        raise ProviderParsingError(
            provider_name, "The player did not provide a stream URL."
        )
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProviderParsingError(
            provider_name, "The player returned an invalid stream URL."
        )
    return value


def _zoko_payload(html: str, provider_name: str) -> dict[str, Any]:
    match = re.search(r"""window\.__P\s*=\s*(["'])(.*?)\1""", html, re.DOTALL)
    if match is None:
        raise ProviderParsingError(
            provider_name, "ZokoAnime's player payload is missing."
        )
    encoded = match.group(2)
    raw = b64decode(encoded + "=" * (-len(encoded) % 4), validate=True)
    decoded = bytes(
        value ^ ZOKO_KEY[index % len(ZOKO_KEY)] for index, value in enumerate(raw)
    )
    payload = json.loads(decoded)
    if not isinstance(payload, dict):
        raise ProviderParsingError(
            provider_name, "ZokoAnime's player payload is invalid."
        )
    return payload


def _megaplay_payload(
    client: Client, html: str, origin: str, headers: dict[str, str], provider_name: str
) -> dict[str, Any]:
    data_id = None
    for element in get_elements_by_tag("div", html):
        candidate = extract_attributes(element).get("data-id", "")
        if candidate.isdigit():
            data_id = candidate
            break
    if data_id is None:
        raise ProviderParsingError(
            provider_name, "MegaPlay's player identifier is missing."
        )
    response = client.get(
        urljoin(origin, "stream/getSources"),
        params={"id": data_id},
        headers=headers,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ProviderParsingError(
            provider_name, "MegaPlay returned an invalid response."
        )
    sources = payload.get("sources")
    url = sources.get("file") if isinstance(sources, dict) else None
    if not url and isinstance(payload.get("enc"), str):
        try:
            encoded = payload["enc"]
            encrypted = b64decode(
                encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True
            )
            cipher = AES.new(MEGAPLAY_KEY, AES.MODE_CBC, iv=MEGAPLAY_IV)
            decoded = json.loads(unpad(cipher.decrypt(encrypted), AES.block_size))
            url = decoded.get("file") if isinstance(decoded, dict) else None
        except ValueError as error:
            raise ProviderParsingError(
                provider_name,
                "MegaPlay decryption failed; its player format may have changed.",
            ) from error
    return {"src": _web_url(url, provider_name), "subtitles": payload.get("tracks", [])}


def _hls_links(
    client: Client,
    url: str,
    headers: dict[str, str],
    params: EpisodeStreamsParams,
    provider_name: str,
) -> list[EpisodeStream]:
    response = client.get(url, headers=headers, follow_redirects=True)
    response.raise_for_status()
    if not response.text.lstrip("\ufeff \r\n\t").startswith("#EXTM3U"):
        raise ProviderParsingError(
            provider_name, "The media server did not return an HLS playlist."
        )
    links: list[EpisodeStream] = []
    height = None
    for raw_line in response.text.splitlines():
        line = raw_line.strip()
        if line.startswith("#EXT-X-STREAM-INF:"):
            resolution = re.search(r"(?:[:,])RESOLUTION=\d+x(\d+)(?:,|$)", line)
            height = resolution.group(1) if resolution else None
        elif line and not line.startswith("#") and height is not None:
            links.append(
                EpisodeStream(
                    link=_web_url(urljoin(str(response.url), line), provider_name),
                    quality=height,
                    translation_type=MediaTranslationType(params.translation_type),
                    hls=True,
                    format="HLS",
                )
            )
            height = None
    if not links:
        raise ProviderParsingError(
            provider_name, "The HLS playlist did not expose usable video resolutions."
        )
    return sorted(links, key=lambda link: int(link.quality), reverse=True)


def extract_server(
    client: Client,
    name: ProviderServer,
    embed_url: str,
    params: EpisodeStreamsParams,
    *,
    provider_name: str,
    embed_referer: str | None = None,
) -> Server:
    parsed = urlsplit(_web_url(embed_url, provider_name))
    if parsed.hostname != EMBED_HOSTS[name]:
        raise ProviderParsingError(provider_name, f"Unexpected host for {name.value}.")
    origin = f"{parsed.scheme}://{parsed.netloc}/"
    headers = {"Referer": origin, "User-Agent": client.headers["User-Agent"]}
    response = client.get(
        embed_url,
        headers={**headers, "Referer": embed_referer or origin},
        follow_redirects=True,
    )
    response.raise_for_status()
    if name is ProviderServer.ZOKOANIME:
        payload = _zoko_payload(response.text, provider_name)
    else:
        payload = _megaplay_payload(
            client, response.text, origin, headers, provider_name
        )
    links = _hls_links(
        client,
        _web_url(payload.get("src"), provider_name),
        headers,
        params,
        provider_name,
    )
    subtitles: list[Subtitle] = []
    if params.subtitles:
        for track in payload.get("subtitles") or []:
            if not isinstance(track, dict):
                continue
            if track.get("kind") not in (None, "captions", "subtitles"):
                continue
            url = track.get("src") or track.get("file")
            if isinstance(url, str) and url:
                subtitles.append(
                    Subtitle(
                        url=_web_url(urljoin(embed_url, url), provider_name),
                        language=track.get("lang") or track.get("label"),
                    )
                )
    return Server(name=name.value, links=links, headers=headers, subtitles=subtitles)
