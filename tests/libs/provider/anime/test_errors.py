from collections.abc import Iterator

import httpx
import pytest
from pytest_httpx import HTTPXMock

from viu_media.core.exceptions import ProviderAPIError
from viu_media.libs.provider.anime.hianime.provider import HiAnime
from viu_media.libs.provider.anime.params import SearchParams
from viu_media.libs.provider.anime.utils.debug import debug_provider


def test_blocked_provider_search_reports_the_api_error(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VIU_DEBUG", raising=False)
    httpx_mock.add_response(status_code=403)
    with httpx.Client() as client:
        with pytest.raises(ProviderAPIError, match="403.*browser verification"):
            HiAnime(client).search(SearchParams(query="Naruto"))


def test_network_failure_is_not_an_empty_search(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VIU_DEBUG", raising=False)
    httpx_mock.add_exception(httpx.ReadTimeout("Timed out"))
    with httpx.Client() as client:
        with pytest.raises(ProviderAPIError, match="ReadTimeout"):
            HiAnime(client).search(SearchParams(query="Naruto"))


def test_debug_mode_preserves_the_original_exception(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIU_DEBUG", "1")
    httpx_mock.add_response(status_code=403)
    with httpx.Client() as client:
        with pytest.raises(httpx.HTTPStatusError):
            HiAnime(client).search(SearchParams(query="Naruto"))


def test_lazy_requests_report_errors_during_iteration(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VIU_DEBUG", raising=False)
    httpx_mock.add_response(status_code=503)

    class LazyProvider:
        @debug_provider
        def stream(self, client: httpx.Client) -> Iterator[str]:
            response = client.get("https://video.example/")
            response.raise_for_status()
            yield response.text

    with httpx.Client() as client:
        streams = LazyProvider().stream(client)
        with pytest.raises(ProviderAPIError, match="503"):
            next(streams)
