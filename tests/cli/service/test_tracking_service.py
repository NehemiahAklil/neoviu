"""TrackingService tests with fake AniList/MyAnimeList clients (no network)."""

import json
from typing import Dict, List, Optional

import pytest

from viu_media.cli.config.generate import generate_config_toml_from_app_model
from viu_media.cli.config.loader import ConfigLoader
from viu_media.cli.service.auth import AuthService
from viu_media.cli.service.tracking import (
    ANILIST,
    MYANIMELIST,
    TrackingError,
    TrackingService,
)
from viu_media.cli.service.tracking.service import MAL_CLIENT_ID_ENV
from viu_media.core.config import AppConfig
from viu_media.libs.media_api.myanimelist import MalListEntry, MalToken
from viu_media.libs.media_api.types import (
    MediaItem,
    MediaSearchResult,
    MediaTitle,
    PageInfo,
    UserListItem,
    UserMediaListStatus,
    UserProfile,
)

WATCHING = UserMediaListStatus.WATCHING
PLANNING = UserMediaListStatus.PLANNING


@pytest.fixture
def user_config(tmp_path, monkeypatch):
    """Points auth.json and config.toml at a temporary directory."""
    import viu_media.cli.service.auth.service as auth_service
    import viu_media.core.constants as constants

    monkeypatch.setattr(auth_service, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.setattr(auth_service, "APP_DATA_DIR", tmp_path)
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr(constants, "USER_CONFIG", config_path)
    monkeypatch.delenv(MAL_CLIENT_ID_ENV, raising=False)
    return config_path


def make_item(
    media_id: int,
    id_mal: Optional[int] = None,
    status: Optional[UserMediaListStatus] = None,
    progress: int = 0,
) -> MediaItem:
    return MediaItem(
        id=media_id,
        id_mal=id_mal,
        title=MediaTitle(english=f"Anime {media_id}"),
        episodes=12,
        user_status=UserListItem(status=status, progress=progress) if status else None,
    )


class FakeAniList:
    def __init__(self, logged_in: bool = True) -> None:
        self.logged_in = logged_in
        self.updates: List = []
        self.deleted: List[int] = []
        self.searches: List = []
        self.by_mal: Dict[int, MediaItem] = {}

    def is_authenticated(self) -> bool:
        return self.logged_in

    def authenticate(self, token: str) -> Optional[UserProfile]:
        self.logged_in = token == "good-token"
        return UserProfile(id=1, name="ani-user") if self.logged_in else None

    def update_list_entry(self, params) -> bool:
        self.updates.append(params)
        return True

    def delete_list_entry(self, media_id: int) -> bool:
        self.deleted.append(media_id)
        return True

    def search_media(self, params) -> MediaSearchResult:
        self.searches.append(params)
        media = [self.by_mal[i] for i in params.id_mal_in or [] if i in self.by_mal]
        return MediaSearchResult(
            page_info=PageInfo(total=len(media), per_page=len(media)), media=media
        )


class FakeMal:
    def __init__(self, entries: Optional[List[MalListEntry]] = None) -> None:
        self.entries = entries or []
        self.updates: List[tuple] = []
        self.deleted: List[int] = []
        self.list_calls = 0
        self.fail_list = False

    def is_authenticated(self) -> bool:
        return True

    def get_user_list(self, status=None):
        self.list_calls += 1
        if self.fail_list:
            return None
        return [e for e in self.entries if status is None or e.status == status]

    def update_list_status(self, mal_id, status=None, progress=None, score=None):
        self.updates.append((mal_id, status, progress, score))
        return True

    def delete_list_status(self, mal_id: int) -> bool:
        self.deleted.append(mal_id)
        return True


def make_service(
    remote: str,
    anilist: Optional[FakeAniList] = None,
    mal: Optional[FakeMal] = None,
) -> TrackingService:
    config = AppConfig()
    config.tracking.remote = remote  # type: ignore[assignment]
    service = TrackingService(config, anilist or FakeAniList())  # type: ignore[arg-type]
    service._mal = mal  # type: ignore[assignment]
    service._mal_checked = True
    return service


@pytest.mark.parametrize(
    "remote, expected",
    [
        ("none", []),
        ("anilist", [ANILIST]),
        ("myanimelist", [MYANIMELIST]),
        ("both", [ANILIST, MYANIMELIST]),
    ],
)
def test_enabled_trackers_follow_the_mode(remote, expected):
    assert make_service(remote).enabled_trackers == expected


def test_set_remote_only_rewrites_tracking_settings(user_config):
    saved = AppConfig()
    saved.general.interface = "grid"
    user_config.write_text(generate_config_toml_from_app_model(saved))

    service = make_service("anilist")
    service.set_remote("both")

    assert service.remote == "both"
    reloaded = ConfigLoader(config_path=user_config).load(allow_setup=False)
    assert reloaded.tracking.remote == "both"
    assert reloaded.general.interface == "grid"


def test_set_remote_without_persisting_leaves_the_file_alone(user_config):
    make_service("anilist").set_remote("none", persist=False)
    assert not user_config.exists()


def test_mal_credentials_are_trimmed_and_saved(user_config):
    service = make_service("myanimelist")
    service.set_mal_credentials("  my-client  ", " secret ")

    assert service.mal_client_id == "my-client"
    reloaded = ConfigLoader(config_path=user_config).load(allow_setup=False)
    assert reloaded.tracking.mal_client_id == "my-client"
    assert reloaded.tracking.mal_client_secret == "secret"


def test_mal_client_id_falls_back_to_the_environment(monkeypatch):
    monkeypatch.setenv(MAL_CLIENT_ID_ENV, "from-env")
    assert make_service("myanimelist").mal_client_id == "from-env"


def test_list_source_prefers_a_logged_in_tracker():
    assert make_service("both", FakeAniList(), FakeMal()).list_source == ANILIST
    logged_out = FakeAniList(logged_in=False)
    assert make_service("both", logged_out, FakeMal()).list_source == MYANIMELIST
    assert make_service("both", logged_out).list_source is None
    assert make_service("none").list_source is None
    assert make_service("both", logged_out, FakeMal()).missing_logins() == [ANILIST]


def test_update_reaches_every_enabled_tracker():
    anilist, mal = FakeAniList(), FakeMal()
    service = make_service("both", anilist, mal)

    results = service.update(make_item(1, id_mal=101), WATCHING, "3", 8.4)

    assert results == {ANILIST: True, MYANIMELIST: True}
    [params] = anilist.updates
    assert (params.media_id, params.status, params.progress, params.score) == (
        1,
        WATCHING,
        "3",
        8.4,
    )
    assert mal.updates == [(101, WATCHING, 3, 8.4)]


def test_update_skips_disabled_and_logged_out_trackers():
    anilist, mal = FakeAniList(logged_in=False), FakeMal()
    assert make_service("anilist", anilist, mal).update(make_item(1, 101)) == {}
    assert anilist.updates == [] and mal.updates == []


def test_update_reports_items_without_a_mal_id_as_failed():
    mal = FakeMal()
    results = make_service("myanimelist", mal=mal).update(make_item(1), progress=2)
    assert results == {MYANIMELIST: False}
    assert mal.updates == []


def test_add_if_missing_never_overwrites_existing_entries():
    anilist = FakeAniList()
    mal = FakeMal([MalListEntry(mal_id=101, title="Listed", status=WATCHING)])
    service = make_service("both", anilist, mal)

    listed = make_item(1, id_mal=101, status=WATCHING, progress=4)
    assert service.add_if_missing(listed) == []
    assert anilist.updates == [] and mal.updates == []

    added = service.add_if_missing(make_item(2, id_mal=102))
    assert added == [ANILIST, MYANIMELIST]
    assert anilist.updates[0].status == PLANNING
    assert mal.updates == [(102, PLANNING, None, None)]


def test_add_if_missing_does_not_trust_a_failed_mal_read():
    mal = FakeMal()
    mal.fail_list = True
    service = make_service("myanimelist", mal=mal)
    assert service.add_if_missing(make_item(2, id_mal=102)) == []
    assert mal.updates == []


def test_list_entries_reads_each_tracker():
    mal = FakeMal([MalListEntry(mal_id=101, title="x", status=PLANNING)])
    service = make_service("both", FakeAniList(), mal)

    entries = service.list_entries(
        make_item(1, id_mal=101, status=WATCHING, progress=5)
    )

    anilist_entry, mal_entry = entries[ANILIST], entries[MYANIMELIST]
    assert anilist_entry is not None and anilist_entry.progress == 5
    assert mal_entry is not None and mal_entry.status == PLANNING
    assert service.list_entries(make_item(2, id_mal=999))[MYANIMELIST] is None


def test_mal_lists_are_resolved_to_anilist_media_and_cached():
    anilist = FakeAniList(logged_in=False)
    anilist.by_mal = {11: make_item(1, id_mal=11), 12: make_item(2, id_mal=12)}
    mal = FakeMal(
        [
            MalListEntry(mal_id=11, title="a", status=WATCHING, progress=2, score=7),
            MalListEntry(mal_id=12, title="b", status=WATCHING, progress=5),
            MalListEntry(mal_id=13, title="no match", status=WATCHING),
            MalListEntry(mal_id=14, title="planned", status=PLANNING),
        ]
    )
    service = make_service("myanimelist", anilist, mal)

    page = service.get_user_list(WATCHING, page=1, per_page=10)

    assert page is not None and page.page_info.total == 3
    assert [m.id for m in page.media] == [1, 2]
    first = page.media[0].user_status
    assert first is not None and (first.progress, first.score) == (2, 7.0)
    assert anilist.searches[0].id_mal_in == [11, 12, 13]

    service.get_user_list(WATCHING, page=1, per_page=10)
    assert mal.list_calls == 1  # served from the short-lived cache
    service.update(make_item(1, id_mal=11), progress=3)
    service.get_user_list(WATCHING, page=1, per_page=10)
    assert mal.list_calls == 2  # writes invalidate the cache


def test_delete_removes_from_each_tracker():
    anilist, mal = FakeAniList(), FakeMal()
    results = make_service("both", anilist, mal).delete(make_item(1, id_mal=101))
    assert results == {ANILIST: True, MYANIMELIST: True}
    assert anilist.deleted == [1] and mal.deleted == [101]


def test_anilist_login_saves_the_profile(user_config):
    service = make_service("anilist", FakeAniList(logged_in=False))

    with pytest.raises(TrackingError):
        service.login_anilist("bad-token")
    assert AuthService(ANILIST).get_auth() is None

    assert service.login_anilist(" good-token ").name == "ani-user"
    saved = AuthService(ANILIST).get_auth()
    assert saved is not None and saved.token == "good-token"


def test_mal_login_needs_a_client_id(user_config):
    with pytest.raises(TrackingError, match="client ID"):
        make_service("myanimelist").begin_mal_login()


def test_mal_login_checks_state_and_saves_tokens(user_config, monkeypatch):
    service = make_service("myanimelist")
    service.config.tracking.mal_client_id = "client"
    request = service.begin_mal_login()
    assert "code_challenge_method=plain" in request.url
    assert request.redirect_uri == "http://localhost:8123/callback"

    with pytest.raises(TrackingError, match="does not match"):
        service.complete_mal_login(request, "code=abc&state=forged")

    class FakeClient:
        def exchange_code(self, code, verifier, redirect_uri):
            assert (code, verifier) == ("abc", request.code_verifier)
            return MalToken(
                access_token="access", refresh_token="refresh", expires_at=99.0
            )

        def authenticate(self, token):
            return UserProfile(id=7, name="mal-user")

        def is_authenticated(self):
            return True

    monkeypatch.setattr(service, "_new_mal_client", FakeClient)
    url = f"http://localhost:8123/callback?code=abc&state={request.state}"
    assert service.complete_mal_login(request, url).name == "mal-user"

    saved = AuthService(MYANIMELIST).get_auth()
    assert saved is not None
    assert (saved.token, saved.refresh_token, saved.expires_at) == (
        "access",
        "refresh",
        99.0,
    )
    assert service.mal is not None


def test_logout_keeps_the_other_trackers_login(user_config):
    profile = UserProfile(id=1, name="someone")
    AuthService(ANILIST).save_user_profile(profile, "a-token")
    AuthService(MYANIMELIST).save_user_profile(profile, "m-token", "refresh", 1.0)

    make_service("both", FakeAniList(), FakeMal()).logout(MYANIMELIST)

    assert AuthService(MYANIMELIST).get_auth() is None
    kept = AuthService(ANILIST).get_auth()
    assert kept is not None and kept.token == "a-token"


def test_auth_files_from_before_refresh_tokens_still_load(user_config, tmp_path):
    (tmp_path / "auth.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "profiles": {
                    "anilist": {
                        "user_profile": {"id": 3, "name": "old"},
                        "token": "legacy",
                    }
                },
            }
        )
    )
    profile = AuthService(ANILIST).get_auth()
    assert profile is not None
    assert (profile.token, profile.refresh_token, profile.expires_at) == (
        "legacy",
        None,
        None,
    )


def test_tracking_defaults():
    tracking = AppConfig().tracking
    assert tracking.remote == "anilist"
    assert tracking.prompt_login is True
    assert tracking.mal_redirect_port == 8123
    assert AppConfig().general.interface == "classic"
