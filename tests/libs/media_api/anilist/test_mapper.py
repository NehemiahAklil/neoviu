from typing import Any

from viu_media.libs.media_api._media_tags import MediaTag
from viu_media.libs.media_api.anilist.mapper import (
    _to_generic_genres,
    _to_generic_tags,
    to_generic_user_profile,
)
from viu_media.libs.media_api.anilist.types import AnilistViewerData
from viu_media.libs.media_api.types import MediaGenre, UserProfile


def test_to_generic_user_profile_success():
    data: AnilistViewerData = {
        "data": {
            "Viewer": {
                "id": 123,
                "name": "testuser",
                "avatar": {
                    "large": "https://example.com/avatar.png",
                    "medium": "https://example.com/avatar_medium.png",
                    "extraLarge": "https://example.com/avatar_extraLarge.png",
                    "small": "https://example.com/avatar_small.png",
                },
                "bannerImage": "https://example.com/banner.png",
                "token": "test_token",
            }
        }
    }
    profile = to_generic_user_profile(data)
    assert isinstance(profile, UserProfile)
    assert profile.id == 123
    assert profile.name == "testuser"
    assert profile.avatar_url == "https://example.com/avatar.png"
    assert profile.banner_url == "https://example.com/banner.png"


def test_to_generic_user_profile_data_none():
    data: Any = {"data": None}
    profile = to_generic_user_profile(data)
    assert profile is None


def test_to_generic_user_profile_no_data_key():
    data: Any = {"errors": [{"message": "Invalid token"}]}
    profile = to_generic_user_profile(data)
    assert profile is None


def test_to_generic_user_profile_no_viewer_key():
    data: Any = {"data": {"Page": {}}}
    profile = to_generic_user_profile(data)
    assert profile is None


def test_to_generic_user_profile_viewer_none():
    data: Any = {"data": {"Viewer": None}}
    profile = to_generic_user_profile(data)
    assert profile is None


def test_unknown_tags_are_skipped():
    tags: Any = [
        {"name": "Prophecy", "rank": 60},
        {"name": "Time Skip", "rank": 80},
        None,
        {"name": None},
    ]
    result = _to_generic_tags(tags)
    assert [t.name for t in result] == [MediaTag("Time Skip")]
    assert result[0].rank == 80


def test_unknown_genres_are_skipped():
    assert _to_generic_genres(["Action", "Brand New Genre"]) == [MediaGenre.ACTION]
    assert _to_generic_genres(None) == []
