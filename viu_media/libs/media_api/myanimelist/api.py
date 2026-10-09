"""MyAnimeList v2 API client for list tracking.

MyAnimeList is used only as a list tracker: metadata, covers and streaming
lookups keep coming from AniList, so this client covers OAuth, the viewer
profile and the user's anime list instead of the full ``BaseApiClient``.
"""

import logging
import secrets
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from httpx import Client, HTTPError, Response
from pydantic import BaseModel, ConfigDict

from ..types import UserMediaListStatus, UserProfile

logger = logging.getLogger(__name__)

MAL_AUTHORIZE_URL = "https://myanimelist.net/v1/oauth2/authorize"
MAL_TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"
MAL_API_BASE = "https://api.myanimelist.net/v2"
MAL_PAGE_LIMIT = 1000

MAL_LIST_FIELDS = "list_status,num_episodes,main_picture,alternative_titles"

_TO_MAL_STATUS = {
    UserMediaListStatus.WATCHING: "watching",
    UserMediaListStatus.REPEATING: "watching",
    UserMediaListStatus.PLANNING: "plan_to_watch",
    UserMediaListStatus.COMPLETED: "completed",
    UserMediaListStatus.PAUSED: "on_hold",
    UserMediaListStatus.DROPPED: "dropped",
}

_FROM_MAL_STATUS = {
    "watching": UserMediaListStatus.WATCHING,
    "plan_to_watch": UserMediaListStatus.PLANNING,
    "completed": UserMediaListStatus.COMPLETED,
    "on_hold": UserMediaListStatus.PAUSED,
    "dropped": UserMediaListStatus.DROPPED,
}


class MyAnimeListError(Exception):
    """Raised when MyAnimeList rejects an OAuth request."""


class MalToken(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None


class MalListEntry(BaseModel):
    """One anime on the user's MyAnimeList list."""

    model_config = ConfigDict(frozen=True)

    mal_id: int
    title: str
    english_title: Optional[str] = None
    num_episodes: Optional[int] = None
    picture: Optional[str] = None
    status: Optional[UserMediaListStatus] = None
    progress: int = 0
    score: Optional[float] = None
    updated_at: Optional[str] = None


def to_mal_status(status: UserMediaListStatus) -> str:
    return _TO_MAL_STATUS[status]


def from_mal_status(
    status: Optional[str], is_rewatching: bool = False
) -> Optional[UserMediaListStatus]:
    if is_rewatching:
        return UserMediaListStatus.REPEATING
    if not status:
        return None
    return _FROM_MAL_STATUS.get(status)


def generate_code_verifier() -> str:
    """Returns a PKCE code verifier (43-128 unreserved characters)."""
    return secrets.token_urlsafe(96)[:128]


def build_authorize_url(
    client_id: str, redirect_uri: str, code_verifier: str, state: str
) -> str:
    # MAL only supports the "plain" PKCE method, so the challenge is the verifier.
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "state": state,
            "redirect_uri": redirect_uri,
            "code_challenge": code_verifier,
            "code_challenge_method": "plain",
        }
    )
    return f"{MAL_AUTHORIZE_URL}?{query}"


def _parse_entry(item: Dict[str, Any]) -> MalListEntry:
    node = item.get("node") or {}
    list_status = item.get("list_status") or node.get("my_list_status") or {}
    picture = node.get("main_picture") or {}
    alt_titles = node.get("alternative_titles") or {}
    score = list_status.get("score")
    return MalListEntry(
        mal_id=node["id"],
        title=node.get("title") or "",
        english_title=alt_titles.get("en") or None,
        num_episodes=node.get("num_episodes") or None,
        picture=picture.get("large") or picture.get("medium"),
        status=from_mal_status(
            list_status.get("status"), bool(list_status.get("is_rewatching"))
        ),
        progress=list_status.get("num_episodes_watched") or 0,
        score=float(score) if score else None,
        updated_at=list_status.get("updated_at"),
    )


class MyAnimeListApi:
    """Thin MyAnimeList client; tokens are persisted by the caller."""

    def __init__(self, client: Client, client_id: str, client_secret: str = ""):
        self.http_client = client
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: Optional[str] = None
        self.user_profile: Optional[UserProfile] = None

    # --- OAuth ---------------------------------------------------------------

    def exchange_code(
        self, code: str, code_verifier: str, redirect_uri: str
    ) -> MalToken:
        return self._request_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            }
        )

    def refresh_token(self, refresh_token: str) -> MalToken:
        return self._request_token(
            {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )

    def _request_token(self, data: Dict[str, str]) -> MalToken:
        if not self.client_id:
            raise MyAnimeListError("A MyAnimeList client ID is required.")
        payload = {"client_id": self.client_id, **data}
        if self.client_secret:
            payload["client_secret"] = self.client_secret
        try:
            response = self.http_client.post(MAL_TOKEN_URL, data=payload)
        except HTTPError as e:
            raise MyAnimeListError(f"Could not reach MyAnimeList: {e}") from e
        body = _json_or_empty(response)
        if response.status_code >= 400 or "access_token" not in body:
            message = body.get("message") or body.get("error") or response.text
            raise MyAnimeListError(f"MyAnimeList token request failed: {message}")
        expires_in = body.get("expires_in")
        return MalToken(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=time.time() + float(expires_in) if expires_in else None,
        )

    # --- Account -------------------------------------------------------------

    def authenticate(self, token: str) -> Optional[UserProfile]:
        self.token = token
        self.http_client.headers["Authorization"] = f"Bearer {token}"
        self.user_profile = self.get_viewer_profile()
        if not self.user_profile:
            self.token = None
            self.http_client.headers.pop("Authorization", None)
        return self.user_profile

    def is_authenticated(self) -> bool:
        return self.user_profile is not None

    def get_viewer_profile(self) -> Optional[UserProfile]:
        if not self.token:
            return None
        data = self._get("/users/@me", {"fields": "id,name,picture"})
        if not data or "id" not in data:
            return None
        return UserProfile(
            id=data["id"], name=data.get("name", ""), avatar_url=data.get("picture")
        )

    # --- Anime list ----------------------------------------------------------

    def get_user_list(
        self, status: Optional[UserMediaListStatus] = None
    ) -> Optional[List[MalListEntry]]:
        """Returns every entry for ``status`` (or the whole list), newest first."""
        if not self.token:
            return None
        params: Optional[Dict[str, Any]] = {
            "fields": MAL_LIST_FIELDS,
            "limit": MAL_PAGE_LIMIT,
            "sort": "list_updated_at",
        }
        # MAL has no rewatching filter, so REPEATING is filtered client side.
        if status and status != UserMediaListStatus.REPEATING:
            params["status"] = to_mal_status(status)

        entries: List[MalListEntry] = []
        url: Optional[str] = "/users/@me/animelist"
        while url:
            data = self._get(url, params)
            if data is None:
                return None
            entries.extend(_parse_entry(item) for item in data.get("data", []))
            url = (data.get("paging") or {}).get("next")
            params = None  # the "next" URL already carries the query

        if status is not None:
            entries = [entry for entry in entries if entry.status == status]
        return entries

    def update_list_status(
        self,
        mal_id: int,
        status: Optional[UserMediaListStatus] = None,
        progress: Optional[int] = None,
        score: Optional[float] = None,
    ) -> bool:
        if not self.token:
            return False
        payload: Dict[str, str] = {}
        if status is not None:
            payload["status"] = to_mal_status(status)
            payload["is_rewatching"] = (
                "true" if status == UserMediaListStatus.REPEATING else "false"
            )
        if progress is not None:
            payload["num_watched_episodes"] = str(progress)
        if score is not None:
            payload["score"] = str(max(0, min(10, round(score))))
        if not payload:
            return True
        response = self._send("PATCH", f"/anime/{mal_id}/my_list_status", payload)
        return response is not None

    def delete_list_status(self, mal_id: int) -> bool:
        if not self.token:
            return False
        return self._send("DELETE", f"/anime/{mal_id}/my_list_status") is not None

    # --- HTTP helpers --------------------------------------------------------

    def _get(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        response = self._send("GET", url, params=params)
        return _json_or_empty(response) if response is not None else None

    def _send(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Response]:
        full_url = url if url.startswith("http") else f"{MAL_API_BASE}{url}"
        try:
            response = self.http_client.request(
                method, full_url, data=data, params=params
            )
        except HTTPError as e:
            logger.error(f"MyAnimeList {method} {url} failed: {e}")
            return None
        # Deleting an entry that is not on the list is already the desired state.
        if response.status_code == 404 and method == "DELETE":
            return response
        if response.status_code >= 400:
            logger.error(
                f"MyAnimeList {method} {url} returned {response.status_code}: "
                f"{response.text[:200]}"
            )
            return None
        return response


def _json_or_empty(response: Response) -> Dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
