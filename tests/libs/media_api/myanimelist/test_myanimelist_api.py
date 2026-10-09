"""MyAnimeList client tests against mocked HTTP responses."""

import httpx
import pytest

from viu_media.libs.media_api.myanimelist import (
    MyAnimeListApi,
    MyAnimeListError,
    build_authorize_url,
    generate_code_verifier,
)
from viu_media.libs.media_api.myanimelist.api import (
    MAL_API_BASE,
    MAL_TOKEN_URL,
    from_mal_status,
    to_mal_status,
)
from viu_media.libs.media_api.types import UserMediaListStatus

S = UserMediaListStatus
PROFILE_URL = f"{MAL_API_BASE}/users/@me?fields=id%2Cname%2Cpicture"


@pytest.fixture
def client():
    with httpx.Client() as http:
        yield MyAnimeListApi(http, "client-id", "client-secret")


def login(httpx_mock, client: MyAnimeListApi) -> None:
    httpx_mock.add_response(url=PROFILE_URL, json={"id": 5, "name": "mal-user"})
    assert client.authenticate("token") is not None


def test_status_mapping_round_trips():
    for status in (S.WATCHING, S.PLANNING, S.COMPLETED, S.PAUSED, S.DROPPED):
        assert from_mal_status(to_mal_status(status)) == status
    assert to_mal_status(S.REPEATING) == "watching"
    assert from_mal_status("completed", is_rewatching=True) == S.REPEATING
    assert from_mal_status(None) is None


def test_authorize_url_uses_plain_pkce():
    verifier = generate_code_verifier()
    assert 43 <= len(verifier) <= 128
    url = build_authorize_url("cid", "http://localhost:8123/callback", verifier, "st")
    assert "code_challenge_method=plain" in url
    assert f"code_challenge={verifier}" in url
    assert "state=st" in url


def test_exchange_code_returns_tokens(httpx_mock, client):
    httpx_mock.add_response(
        method="POST",
        url=MAL_TOKEN_URL,
        json={"access_token": "a", "refresh_token": "r", "expires_in": 3600},
    )

    token = client.exchange_code("code", "verifier", "http://localhost/cb")

    assert (token.access_token, token.refresh_token) == ("a", "r")
    assert token.expires_at is not None
    sent = httpx_mock.get_request().content.decode()
    for part in (
        "client_id=client-id",
        "client_secret=client-secret",
        "grant_type=authorization_code",
        "code_verifier=verifier",
    ):
        assert part in sent


def test_token_errors_raise(httpx_mock, client):
    httpx_mock.add_response(
        method="POST", url=MAL_TOKEN_URL, status_code=400, json={"message": "bad"}
    )
    with pytest.raises(MyAnimeListError, match="bad"):
        client.refresh_token("old")


def test_failed_authentication_clears_the_token(httpx_mock, client):
    httpx_mock.add_response(url=PROFILE_URL, status_code=401, json={})
    assert client.authenticate("expired") is None
    assert not client.is_authenticated()
    assert "Authorization" not in client.http_client.headers


def test_user_list_follows_pages_and_filters_rewatching(httpx_mock, client):
    login(httpx_mock, client)
    next_url = f"{MAL_API_BASE}/users/@me/animelist?offset=1000"
    httpx_mock.add_response(
        url=httpx.URL(
            f"{MAL_API_BASE}/users/@me/animelist",
            params={
                "fields": "list_status,num_episodes,main_picture,alternative_titles",
                "limit": 1000,
                "sort": "list_updated_at",
            },
        ),
        json={
            "data": [
                {
                    "node": {
                        "id": 1,
                        "title": "One",
                        "num_episodes": 12,
                        "main_picture": {"large": "big.jpg"},
                        "alternative_titles": {"en": "One EN"},
                    },
                    "list_status": {
                        "status": "watching",
                        "num_episodes_watched": 4,
                        "score": 8,
                    },
                }
            ],
            "paging": {"next": next_url},
        },
    )
    httpx_mock.add_response(
        url=next_url,
        json={
            "data": [
                {
                    "node": {"id": 2, "title": "Two"},
                    "list_status": {"status": "completed", "is_rewatching": True},
                }
            ]
        },
    )

    entries = client.get_user_list()

    assert entries is not None
    assert [(e.mal_id, e.status, e.progress) for e in entries] == [
        (1, S.WATCHING, 4),
        (2, S.REPEATING, 0),
    ]
    assert entries[0].english_title == "One EN" and entries[0].score == 8.0
    assert entries[0].picture == "big.jpg"


def test_update_sends_a_form_patch(httpx_mock, client):
    login(httpx_mock, client)
    httpx_mock.add_response(
        method="PATCH", url=f"{MAL_API_BASE}/anime/42/my_list_status", json={}
    )

    assert client.update_list_status(42, S.REPEATING, progress=3, score=7.6)

    sent = httpx_mock.get_requests()[-1].content.decode()
    for part in (
        "status=watching",
        "is_rewatching=true",
        "num_watched_episodes=3",
        "score=8",
    ):
        assert part in sent


def test_nothing_is_sent_without_changes_or_login(client):
    assert client.update_list_status(42) is False  # not logged in
    client.token = "token"
    assert client.update_list_status(42) is True  # nothing to change


def test_deleting_an_unlisted_anime_succeeds(httpx_mock, client):
    login(httpx_mock, client)
    httpx_mock.add_response(
        method="DELETE", url=f"{MAL_API_BASE}/anime/42/my_list_status", status_code=404
    )
    assert client.delete_list_status(42) is True


def test_server_errors_are_reported_as_failures(httpx_mock, client):
    login(httpx_mock, client)
    httpx_mock.add_response(
        method="PATCH", url=f"{MAL_API_BASE}/anime/42/my_list_status", status_code=500
    )
    assert client.update_list_status(42, progress=1) is False
