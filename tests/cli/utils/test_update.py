import pytest

from viu_media.cli.utils.update import parse_version


@pytest.mark.parametrize(
    "older, newer",
    [
        ("0.0.8a1", "0.0.8a2"),
        ("0.0.8a2", "0.0.8b1"),
        ("0.0.8b1", "0.0.8rc1"),
        ("0.0.8rc1", "0.0.8"),
        ("0.0.8", "0.0.9a1"),
        ("0.0.9", "0.1.0"),
        ("v0.1.0", "1.0.0"),
        ("garbage", "0.0.1"),
    ],
)
def test_parse_version_orders_releases(older, newer):
    assert parse_version(older) < parse_version(newer)


@pytest.mark.parametrize(
    "a, b",
    [("v0.0.8a1", "0.0.8a1"), ("0.0.8-alpha.1", "0.0.8a1"), ("1.2", "1.2.0")],
)
def test_parse_version_treats_spellings_as_equal(a, b):
    assert parse_version(a) == parse_version(b)
