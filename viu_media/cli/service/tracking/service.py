"""Keeps the user's AniList and MyAnimeList lists in sync with viu.

The tracking mode mirrors curd: history is always kept locally, and
``tracking.remote`` decides which sites also receive status, progress and
score changes. AniList stays the metadata source; MyAnimeList entries are
resolved to AniList media through their MAL ids.
"""

import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Set, Tuple

from ....core.config.model import AppConfig
from ....libs.media_api.base import BaseApiClient
from ....libs.media_api.myanimelist import (
    MalListEntry,
    MyAnimeListApi,
    MyAnimeListError,
    build_authorize_url,
    generate_code_verifier,
)
from ....libs.media_api.params import (
    MediaSearchParams,
    UpdateUserMediaListEntryParams,
    UserMediaListSearchParams,
)
from ....libs.media_api.types import (
    MediaItem,
    MediaSearchResult,
    PageInfo,
    UserListItem,
    UserMediaListStatus,
    UserProfile,
)
from ..auth import AuthService
from .oauth import parse_callback, wait_for_callback

logger = logging.getLogger(__name__)

ANILIST = "anilist"
MYANIMELIST = "myanimelist"
TRACKERS = (ANILIST, MYANIMELIST)
TrackerName = Literal["anilist", "myanimelist"]
RemoteMode = Literal["none", "anilist", "myanimelist", "both"]

TRACKER_LABELS = {ANILIST: "AniList", MYANIMELIST: "MyAnimeList"}

MAL_CLIENT_ID_ENV = "VIU_MAL_CLIENT_ID"
MAL_CLIENT_SECRET_ENV = "VIU_MAL_CLIENT_SECRET"
_MAL_LIST_TTL = 120.0
_ANILIST_BATCH = 50


class TrackingError(Exception):
    """A user-facing tracking problem, such as a failed login."""


@dataclass(frozen=True)
class TrackerState:
    name: str
    label: str
    enabled: bool
    logged_in: bool
    username: Optional[str] = None


@dataclass(frozen=True)
class MalLoginRequest:
    url: str
    state: str
    code_verifier: str
    redirect_uri: str
    port: int


class TrackingService:
    def __init__(self, config: AppConfig, media_api: Optional[BaseApiClient] = None):
        self.config = config
        self._media_api = media_api
        self._anilist_client: Optional[BaseApiClient] = None
        self._mal: Optional[MyAnimeListApi] = None
        self._mal_checked = False
        self._mal_lists: Dict[
            Optional[UserMediaListStatus], Tuple[float, List[MalListEntry]]
        ] = {}
        self._mal_to_media: Dict[int, MediaItem] = {}
        self._lock = threading.RLock()
        # Login prompts already shown this session, so the UI asks only once.
        self.prompted: Set[str] = set()

    # --- configuration -------------------------------------------------------

    @property
    def remote(self) -> RemoteMode:
        return self.config.tracking.remote

    @property
    def enabled_trackers(self) -> List[str]:
        remote = self.remote
        if remote == "both":
            return [ANILIST, MYANIMELIST]
        if remote in TRACKERS:
            return [remote]
        return []

    def is_enabled(self, tracker: str) -> bool:
        return tracker in self.enabled_trackers

    def set_remote(self, remote: RemoteMode, persist: bool = True) -> None:
        """Switches the tracking mode and optionally saves it to the config file."""
        self.config.tracking.remote = remote
        self._mal_lists.clear()
        if persist:
            _persist_tracking(remote=remote)

    def set_mal_credentials(
        self, client_id: str, client_secret: str = "", persist: bool = True
    ) -> None:
        """Stores the MyAnimeList API client used for logging in."""
        client_id, client_secret = client_id.strip(), client_secret.strip()
        self.config.tracking.mal_client_id = client_id
        self.config.tracking.mal_client_secret = client_secret
        with self._lock:
            self._mal = None
            self._mal_checked = False
        if persist:
            _persist_tracking(mal_client_id=client_id, mal_client_secret=client_secret)

    @property
    def mal_client_id(self) -> str:
        return self.config.tracking.mal_client_id or os.environ.get(
            MAL_CLIENT_ID_ENV, ""
        )

    @property
    def mal_client_secret(self) -> str:
        return self.config.tracking.mal_client_secret or os.environ.get(
            MAL_CLIENT_SECRET_ENV, ""
        )

    @property
    def mal_redirect_uri(self) -> str:
        return f"http://localhost:{self.config.tracking.mal_redirect_port}/callback"

    # --- clients -------------------------------------------------------------

    @property
    def anilist(self) -> BaseApiClient:
        """The AniList client, authenticated when the user is logged in."""
        with self._lock:
            if self._anilist_client is None:
                if (
                    self._media_api is not None
                    and self.config.general.media_api == ANILIST
                ):
                    self._anilist_client = self._media_api
                else:
                    from ....libs.media_api.api import create_api_client

                    client = create_api_client(ANILIST, self.config)
                    if profile := AuthService(ANILIST).get_auth():
                        _safe_authenticate(client, profile.token)
                    self._anilist_client = client
            return self._anilist_client

    @property
    def mal(self) -> Optional[MyAnimeListApi]:
        """An authenticated MyAnimeList client, refreshing the token if needed."""
        with self._lock:
            if self._mal_checked:
                return self._mal if self._mal and self._mal.is_authenticated() else None
            self._mal_checked = True
            auth = AuthService(MYANIMELIST)
            profile = auth.get_auth()
            if not profile:
                return None
            client = self._new_mal_client()
            token = profile.token
            expired = profile.expires_at and profile.expires_at - 60 < time.time()
            if expired and profile.refresh_token:
                token = self._refresh_mal(client, auth, profile.refresh_token) or token
            if not _safe_authenticate(client, token) and profile.refresh_token:
                if refreshed := self._refresh_mal(client, auth, profile.refresh_token):
                    _safe_authenticate(client, refreshed)
            self._mal = client
            return client if client.is_authenticated() else None

    def _new_mal_client(self) -> MyAnimeListApi:
        import httpx

        return MyAnimeListApi(
            httpx.Client(timeout=20), self.mal_client_id, self.mal_client_secret
        )

    def _refresh_mal(
        self, client: MyAnimeListApi, auth: AuthService, refresh_token: str
    ) -> Optional[str]:
        try:
            token = client.refresh_token(refresh_token)
        except MyAnimeListError as e:
            logger.warning(f"Could not refresh the MyAnimeList token: {e}")
            return None
        profile = auth.get_auth()
        if profile:
            auth.save_user_profile(
                profile.user_profile,
                token.access_token,
                token.refresh_token or refresh_token,
                token.expires_at,
            )
        return token.access_token

    # --- status --------------------------------------------------------------

    def is_logged_in(self, tracker: str) -> bool:
        if tracker == ANILIST:
            return self.anilist.is_authenticated()
        if tracker == MYANIMELIST:
            return self.mal is not None
        return False

    def username(self, tracker: str) -> Optional[str]:
        profile = AuthService(tracker).get_auth()
        return profile.user_profile.name if profile else None

    def states(self) -> List[TrackerState]:
        return [
            TrackerState(
                name=tracker,
                label=TRACKER_LABELS[tracker],
                enabled=self.is_enabled(tracker),
                logged_in=self.is_logged_in(tracker),
                username=self.username(tracker),
            )
            for tracker in TRACKERS
        ]

    def missing_logins(self) -> List[str]:
        """Enabled trackers the user still has to log in to."""
        return [t for t in self.enabled_trackers if not self.is_logged_in(t)]

    @property
    def list_source(self) -> Optional[str]:
        """The logged-in tracker whose lists are shown, preferring AniList."""
        for tracker in self.enabled_trackers:
            if self.is_logged_in(tracker):
                return tracker
        return None

    @property
    def can_track(self) -> bool:
        return self.list_source is not None

    # --- login ---------------------------------------------------------------

    @property
    def anilist_login_url(self) -> str:
        from ....core.constants import ANILIST_AUTH

        return ANILIST_AUTH

    def login_anilist(self, token: str) -> UserProfile:
        token = token.strip()
        if not token:
            raise TrackingError("No AniList token was provided.")
        profile = _safe_authenticate(self.anilist, token)
        if not profile:
            raise TrackingError("AniList rejected the token. It may be expired.")
        AuthService(ANILIST).save_user_profile(profile, token)
        return profile

    def begin_mal_login(self) -> MalLoginRequest:
        if not self.mal_client_id:
            raise TrackingError(
                "MyAnimeList needs your own API client ID. Create an app at "
                "https://myanimelist.net/apiconfig with the redirect URL "
                f"{self.mal_redirect_uri}, then set tracking.mal_client_id "
                f"(or {MAL_CLIENT_ID_ENV})."
            )
        verifier = generate_code_verifier()
        state = secrets.token_urlsafe(16)
        return MalLoginRequest(
            url=build_authorize_url(
                self.mal_client_id, self.mal_redirect_uri, verifier, state
            ),
            state=state,
            code_verifier=verifier,
            redirect_uri=self.mal_redirect_uri,
            port=self.config.tracking.mal_redirect_port,
        )

    def wait_for_mal_redirect(
        self,
        request: MalLoginRequest,
        timeout: float = 180,
        cancel: Optional[threading.Event] = None,
    ) -> Optional[str]:
        """Waits for the browser redirect; returns the callback query or ``None``.

        Raises ``OSError`` when the callback port is busy.
        """
        callback = wait_for_callback(request.port, timeout, cancel)
        if callback is None:
            return None
        if callback.error:
            raise TrackingError(f"MyAnimeList login was denied: {callback.error}")
        query = f"code={callback.code}"
        if callback.state:
            query += f"&state={callback.state}"
        return query

    def complete_mal_login(
        self, request: MalLoginRequest, code_or_url: str
    ) -> UserProfile:
        callback = parse_callback(code_or_url)
        if callback.error or not callback.code:
            raise TrackingError(callback.error or "No authorization code was found.")
        if callback.state and callback.state != request.state:
            raise TrackingError("The login response does not match this request.")
        client = self._new_mal_client()
        try:
            token = client.exchange_code(
                callback.code, request.code_verifier, request.redirect_uri
            )
        except MyAnimeListError as e:
            raise TrackingError(str(e)) from e
        profile = _safe_authenticate(client, token.access_token)
        if not profile:
            raise TrackingError(
                "MyAnimeList accepted the login but the profile failed to load."
            )
        AuthService(MYANIMELIST).save_user_profile(
            profile, token.access_token, token.refresh_token, token.expires_at
        )
        with self._lock:
            self._mal = client
            self._mal_checked = True
            self._mal_lists.clear()
        return profile

    def logout(self, tracker: str) -> None:
        AuthService(tracker).clear_user_profile()
        with self._lock:
            if tracker == ANILIST and self._anilist_client is not None:
                # authenticate("") resets the client's token, header and profile
                # without a network call.
                _safe_authenticate(self._anilist_client, "")
            elif tracker == MYANIMELIST:
                self._mal = None
                self._mal_checked = True
                self._mal_lists.clear()

    # --- reading lists -------------------------------------------------------

    def get_user_list(
        self,
        status: UserMediaListStatus,
        page: int = 1,
        per_page: Optional[int] = None,
    ) -> Optional[MediaSearchResult]:
        source = self.list_source
        per_page = per_page or self.config.anilist.per_page or 15
        if source == ANILIST:
            return self.anilist.search_media_list(
                UserMediaListSearchParams(status=status, page=page, per_page=per_page)
            )
        if source == MYANIMELIST:
            return self._get_mal_page(status, page, per_page)
        return None

    def _mal_entries(
        self, status: Optional[UserMediaListStatus]
    ) -> Optional[List[MalListEntry]]:
        mal = self.mal
        if mal is None:
            return None
        with self._lock:
            cached = self._mal_lists.get(status)
            if cached and time.monotonic() - cached[0] < _MAL_LIST_TTL:
                return cached[1]
        entries = mal.get_user_list(status)
        if entries is not None:
            with self._lock:
                self._mal_lists[status] = (time.monotonic(), entries)
        return entries

    def _get_mal_page(
        self, status: UserMediaListStatus, page: int, per_page: int
    ) -> Optional[MediaSearchResult]:
        entries = self._mal_entries(status)
        if entries is None:
            return None
        start = (page - 1) * per_page
        page_entries = entries[start : start + per_page]
        resolved = self._resolve_mal_ids([e.mal_id for e in page_entries])
        media: List[MediaItem] = []
        for entry in page_entries:
            item = resolved.get(entry.mal_id)
            if item is None:
                logger.info(
                    f"MAL entry {entry.mal_id} ({entry.title}) has no AniList match"
                )
                continue
            media.append(
                item.model_copy(
                    update={
                        "user_status": UserListItem(
                            status=entry.status,
                            progress=entry.progress,
                            score=entry.score,
                        )
                    }
                )
            )
        return MediaSearchResult(
            page_info=PageInfo(
                total=len(entries),
                current_page=page,
                has_next_page=start + per_page < len(entries),
                per_page=per_page,
            ),
            media=media,
        )

    def _resolve_mal_ids(self, mal_ids: List[int]) -> Dict[int, MediaItem]:
        with self._lock:
            missing = [i for i in mal_ids if i not in self._mal_to_media]
        for start in range(0, len(missing), _ANILIST_BATCH):
            batch = missing[start : start + _ANILIST_BATCH]
            result = self.anilist.search_media(
                MediaSearchParams(id_mal_in=batch, per_page=len(batch))
            )
            with self._lock:
                for item in result.media if result else []:
                    if item.id_mal is not None:
                        self._mal_to_media[item.id_mal] = item
        with self._lock:
            return {
                i: self._mal_to_media[i] for i in mal_ids if i in self._mal_to_media
            }

    def get_mal_status(self, media_item: MediaItem) -> Optional[UserListItem]:
        """The MyAnimeList list entry for an item, if it is on the user's list."""
        mal_id = self._mal_id(media_item)
        if mal_id is None:
            return None
        for entry in self._mal_entries(None) or []:
            if entry.mal_id == mal_id:
                return UserListItem(
                    status=entry.status, progress=entry.progress, score=entry.score
                )
        return None

    def list_entries(self, media_item: MediaItem) -> Dict[str, Optional[UserListItem]]:
        """The item's entry on each enabled, logged-in tracker (None if unlisted).

        The AniList entry is read from ``media_item.user_status``, so pass an
        item freshly fetched from AniList.
        """
        entries: Dict[str, Optional[UserListItem]] = {}
        if self.is_enabled(ANILIST) and self.is_logged_in(ANILIST):
            entries[ANILIST] = (
                media_item.user_status
                if self.config.general.media_api == ANILIST
                else None
            )
        if self.is_enabled(MYANIMELIST) and self.mal is not None:
            entries[MYANIMELIST] = self.get_mal_status(media_item)
        return entries

    # --- writing -------------------------------------------------------------

    def update(
        self,
        media_item: MediaItem,
        status: Optional[UserMediaListStatus] = None,
        progress: Optional[str | int] = None,
        score: Optional[float] = None,
    ) -> Dict[str, bool]:
        """Pushes changes to every enabled, logged-in tracker.

        Returns a ``{tracker: succeeded}`` map; trackers that are disabled or
        logged out are left out.
        """
        episode = _to_episode(progress)
        results: Dict[str, bool] = {}
        if self.is_enabled(ANILIST) and self.is_logged_in(ANILIST):
            anilist_id = self._anilist_id(media_item)
            results[ANILIST] = (
                anilist_id is not None
                and self.anilist.update_list_entry(
                    UpdateUserMediaListEntryParams(
                        media_id=anilist_id,
                        status=status,
                        progress=str(episode) if episode is not None else None,
                        score=score,
                    )
                )
            )
        mal = self.mal if self.is_enabled(MYANIMELIST) else None
        if mal is not None:
            mal_id = self._mal_id(media_item)
            if mal_id is None:
                logger.warning(
                    f"'{media_item.title.english}' has no MyAnimeList id; skipping MAL sync"
                )
                results[MYANIMELIST] = False
            else:
                results[MYANIMELIST] = mal.update_list_status(
                    mal_id, status=status, progress=episode, score=score
                )
            with self._lock:
                self._mal_lists.clear()
        for tracker, ok in results.items():
            log = logger.info if ok else logger.warning
            log(
                f"{TRACKER_LABELS[tracker]} update for {media_item.id} "
                f"(status={status}, progress={episode}, score={score}) "
                f"{'succeeded' if ok else 'failed'}"
            )
        return results

    def add_if_missing(
        self,
        media_item: MediaItem,
        status: UserMediaListStatus = UserMediaListStatus.PLANNING,
    ) -> List[str]:
        """Adds an item to each enabled tracker where it is not listed yet.

        Returns the trackers the item was added to. Existing entries are never
        overwritten.
        """
        added: List[str] = []
        anilist_ready = self.is_enabled(ANILIST) and self.is_logged_in(ANILIST)
        if anilist_ready and self.config.general.media_api == ANILIST:
            if media_item.user_status is None:
                anilist_id = self._anilist_id(media_item)
                if anilist_id is not None and self.anilist.update_list_entry(
                    UpdateUserMediaListEntryParams(media_id=anilist_id, status=status)
                ):
                    added.append(ANILIST)
        mal = self.mal if self.is_enabled(MYANIMELIST) else None
        mal_id = self._mal_id(media_item) if mal is not None else None
        if mal is not None and mal_id is not None:
            # A failed list read must not be mistaken for "not on the list".
            entries = self._mal_entries(None)
            if entries is not None and all(e.mal_id != mal_id for e in entries):
                if mal.update_list_status(mal_id, status=status):
                    added.append(MYANIMELIST)
                    with self._lock:
                        self._mal_lists.clear()
        return added

    def delete(self, media_item: MediaItem) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        if self.is_enabled(ANILIST) and self.is_logged_in(ANILIST):
            anilist_id = self._anilist_id(media_item)
            results[ANILIST] = (
                anilist_id is not None and self.anilist.delete_list_entry(anilist_id)
            )
        mal = self.mal if self.is_enabled(MYANIMELIST) else None
        if mal is not None:
            mal_id = self._mal_id(media_item)
            results[MYANIMELIST] = mal_id is not None and mal.delete_list_status(mal_id)
            with self._lock:
                self._mal_lists.clear()
        return results

    def _anilist_id(self, media_item: MediaItem) -> Optional[int]:
        if self.config.general.media_api == ANILIST:
            return media_item.id
        if media_item.id_mal is None:
            return None
        item = self._resolve_mal_ids([media_item.id_mal]).get(media_item.id_mal)
        return item.id if item else None

    def _mal_id(self, media_item: MediaItem) -> Optional[int]:
        if media_item.id_mal is not None:
            return media_item.id_mal
        if self.config.general.media_api == "jikan":
            return media_item.id
        return None


def _safe_authenticate(client, token: str) -> Optional[UserProfile]:
    import httpx

    try:
        return client.authenticate(token)
    except httpx.HTTPError as e:
        logger.warning(f"Could not reach the tracker to log in: {e}")
        return None


def _to_episode(progress: Optional[str | int]) -> Optional[int]:
    if progress is None or progress == "":
        return None
    try:
        return int(float(progress))
    except (TypeError, ValueError):
        return None


def _persist_tracking(**fields: object) -> None:
    """Writes only the given ``tracking`` fields into the user's config file."""
    from ....core.constants import USER_CONFIG
    from ...config.generate import generate_config_toml_from_app_model
    from ...config.loader import ConfigLoader

    if USER_CONFIG.exists():
        saved = ConfigLoader(config_path=USER_CONFIG).load(allow_setup=False)
    else:
        saved = AppConfig()
    for name, value in fields.items():
        setattr(saved.tracking, name, value)
    USER_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    USER_CONFIG.write_text(generate_config_toml_from_app_model(saved), encoding="utf-8")
