from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from viu_media.cli.config.editor import InteractiveConfigEditor
from viu_media.cli.config.generate import generate_config_toml_from_app_model
from viu_media.cli.interactive.menu.media.media_actions import _change_provider
from viu_media.cli.interactive.session import Context
from viu_media.cli.interactive.state import InternalDirective, MenuName, State
from viu_media.cli.options import _get_click_type, options_from_model
from viu_media.core.config import AppConfig
from viu_media.core.config.model import GeneralConfig, StreamConfig
from viu_media.libs.provider.anime.types import ProviderName


@pytest.mark.parametrize("name", ["animeunity", "hianime", "anipub"])
def test_supported_provider_names_remain_valid_configuration(name: str) -> None:
    config = AppConfig.model_validate({"general": {"provider": name}})
    assert config.general.provider.value == name


@pytest.mark.parametrize("name", ["allanime", "animepahe", "nyaa", "yugen"])
def test_removed_provider_names_are_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"general": {"provider": name}})


def test_cli_lists_only_supported_providers_and_defaults_to_hianime() -> None:
    @click.command()
    @options_from_model(GeneralConfig)
    def command(**kwargs: object) -> None:
        click.echo(kwargs["provider"])

    runner = CliRunner()
    help_result = runner.invoke(command, ["--help"])
    assert "[not working]" not in help_result.output
    for removed in ["allanime", "animepahe", "nyaa", "yugen"]:
        assert removed not in help_result.output
        assert runner.invoke(command, ["--provider", removed]).exit_code == 2
    result = runner.invoke(command, [])
    assert result.exit_code == 0
    assert result.output.strip() == "hianime"


def test_completion_only_includes_supported_provider_values() -> None:
    choice = _get_click_type(GeneralConfig.model_fields["provider"])
    command = click.Command("test")
    completions = choice.shell_complete(
        click.Context(command), click.Option(["--provider"]), ""
    )
    assert {item.value for item in completions} == {
        provider.value for provider in ProviderName
    }
    assert not any("[not working]" in (item.help or "") for item in completions)


def test_media_menu_selects_a_supported_provider() -> None:
    selector = MagicMock()
    selector.choose.return_value = "hianime"
    config = AppConfig.model_validate({"general": {"provider": "animeunity"}})
    context = Context(config=config, _selector=selector)
    context._provider = MagicMock()
    context._player = MagicMock()
    context._download = MagicMock()
    state = State(menu_name=MenuName.MEDIA_ACTIONS)

    assert _change_provider(context, state)() == InternalDirective.RELOAD
    choices = selector.choose.call_args.args[1]
    assert set(choices) == {provider.value for provider in ProviderName}
    assert context.config.general.provider is ProviderName.HIANIME
    assert context._provider is None
    assert context._player is None
    assert context._download is None


def test_cancelled_provider_selection_preserves_the_current_provider() -> None:
    selector = MagicMock()
    selector.choose.return_value = None
    context = Context(config=AppConfig(), _selector=selector)
    provider = MagicMock()
    context._provider = provider
    state = State(menu_name=MenuName.MEDIA_ACTIONS)

    assert _change_provider(context, state)() == InternalDirective.RELOAD
    assert context.config.general.provider is ProviderName.HIANIME
    assert context._provider is provider


def test_configuration_wizard_offers_supported_enum_choices() -> None:
    editor = InteractiveConfigEditor(AppConfig())
    with patch("viu_media.cli.config.editor.inquirer.select") as select:
        prompt = editor._create_prompt(
            "provider",
            GeneralConfig.model_fields["provider"],
            ProviderName.HIANIME,
        )
    assert prompt is select.return_value
    choices = select.call_args.kwargs["choices"]
    assert choices == [
        {"name": provider.value, "value": provider} for provider in ProviderName
    ]
    assert select.call_args.kwargs["default"] is ProviderName.HIANIME


def test_generated_config_has_a_working_default_and_no_retired_choices() -> None:
    config = generate_config_toml_from_app_model(AppConfig())
    assert 'provider = "hianime"' in config
    assert "[not working]" not in config
    for removed in ["allanime", "animepahe", "nyaa", "yugen"]:
        assert removed not in config


def test_quality_prompt_accepts_real_heights_and_rejects_invalid_input() -> None:
    editor = InteractiveConfigEditor(AppConfig())
    with patch("viu_media.cli.config.editor.inquirer.text") as text:
        editor._create_prompt("quality", StreamConfig.model_fields["quality"], "1080")
    validate = text.call_args.kwargs["validate"]
    assert validate("800")
    assert validate("1080")
    assert not validate("0")
    assert not validate("best")
