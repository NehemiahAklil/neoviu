import importlib.util

import pytest

from viu_media.libs.provider.anime.base import BaseAnimeProvider
from viu_media.libs.provider.anime.provider import (
    PROVIDERS_AVAILABLE,
    create_provider,
)
from viu_media.libs.provider.anime.types import ProviderName


@pytest.mark.parametrize("provider_name", ProviderName)
def test_configured_provider_can_be_created(provider_name: ProviderName) -> None:
    provider = create_provider(provider_name)
    try:
        assert isinstance(provider, BaseAnimeProvider)
    finally:
        provider.client.close()


def test_registered_providers_match_configuration_choices() -> None:
    assert set(PROVIDERS_AVAILABLE) == {provider.value for provider in ProviderName}


@pytest.mark.parametrize("provider", ["allanime", "animepahe", "nyaa", "yugen"])
def test_retired_provider_implementations_are_not_installed(provider: str) -> None:
    assert importlib.util.find_spec(f"viu_media.libs.provider.anime.{provider}") is None
