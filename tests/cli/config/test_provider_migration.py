from pathlib import Path

import pytest
from click.testing import CliRunner

from viu_media.cli.cli import cli
from viu_media.cli.config.generate import generate_config_toml_from_app_model
from viu_media.cli.config.loader import ConfigLoader
from viu_media.core.exceptions import ConfigError
from viu_media.libs.provider.anime.types import ProviderName, ProviderServer


@pytest.mark.parametrize("provider", ["allanime", "animepahe", "nyaa", "yugen"])
def test_old_saved_provider_is_migrated_with_a_visible_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], provider: str
) -> None:
    path = tmp_path / "config.toml"
    original = f'[general]\nprovider = "{provider}"\nicons = false\n'
    path.write_text(original)

    config = ConfigLoader(path).load()

    assert config.general.provider is ProviderName.HIANIME
    assert config.general.icons is False
    assert path.read_text() == original
    notice = capsys.readouterr().err
    assert provider in notice and "hianime" in notice
    assert "viu config --update" in notice

    path.write_text(generate_config_toml_from_app_model(config))
    assert ConfigLoader(path).load().general.provider is ProviderName.HIANIME
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("section", ["stream", "downloads"])
@pytest.mark.parametrize(
    "server",
    [
        "sharepoint",
        "dropbox",
        "gogoanime",
        "weTransfer",
        "wixmp",
        "Yt",
        "mp4-upload",
        "kwik",
        "nyaa",
    ],
)
def test_retired_server_preferences_reset_to_top(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], section: str, server: str
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(f'[{section}]\nserver = "{server}"\n')

    config = ConfigLoader(path).load()

    assert getattr(config, section).server is ProviderServer.TOP
    assert server in capsys.readouterr().err


def test_explicit_supported_overrides_take_priority_without_a_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[general]\nprovider = "allanime"\n[stream]\nserver = "dropbox"\n')

    config = ConfigLoader(path).load(
        {"general": {"provider": "animeunity"}, "stream": {"server": "vixcloud"}}
    )

    assert config.general.provider is ProviderName.ANIMEUNITY
    assert config.stream.server is ProviderServer.VIXCLOUD
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("provider", ["unknown-provider", ["allanime"]])
def test_unknown_or_malformed_provider_values_still_fail_validation(
    tmp_path: Path, provider: str | list[str]
) -> None:
    path = tmp_path / "config.toml"
    path.write_text("")
    with pytest.raises(ConfigError):
        ConfigLoader(path).load({"general": {"provider": provider}})


def test_explicit_retired_provider_override_is_not_silently_migrated(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[general]\nprovider = "hianime"\n')
    with pytest.raises(ConfigError):
        ConfigLoader(path).load({"general": {"provider": "allanime"}})


def test_cli_update_persists_migration_in_the_isolated_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[general]\nprovider = "allanime"\nwelcome_screen = false\n'
        "show_new_release = false\ncheck_for_updates = false\n"
    )
    monkeypatch.setattr("viu_media.cli.cli.USER_CONFIG", path)
    monkeypatch.setattr("viu_media.core.constants.USER_CONFIG", path)
    monkeypatch.setattr(
        "viu_media.cli.cli.setup_exceptions_handler", lambda *args: None
    )
    monkeypatch.setattr("viu_media.cli.cli.setup_logging", lambda *args: None)

    result = CliRunner().invoke(cli, ["config", "--update"])

    assert result.exit_code == 0, result.output
    assert "allanime -> hianime" in result.output
    assert 'provider = "hianime"' in path.read_text()
    assert "allanime" not in path.read_text()
