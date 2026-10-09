"""The 'viu tracker' and 'viu tui' commands, with services mocked out."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from viu_media.cli.commands import tracker as tracker_cmd
from viu_media.cli.commands.anilist.cmd import anilist
from viu_media.cli.commands.tui import tui
from viu_media.core.config import AppConfig


@pytest.fixture
def services():
    tracking, selector, feedback = MagicMock(), MagicMock(), MagicMock()
    tracking.enabled_trackers = ["anilist"]
    tracking.missing_logins.return_value = ["anilist"]
    tracking.is_enabled.return_value = True
    with patch.object(
        tracker_cmd, "_services", return_value=(tracking, selector, feedback)
    ):
        yield tracking, selector, feedback


def run(*args: str):
    return CliRunner().invoke(tracker_cmd.tracker, args, obj=AppConfig())


def test_login_with_a_token(services):
    tracking, _, feedback = services
    with patch(
        "viu_media.cli.utils.tracker_login.login_anilist", return_value=True
    ) as login:
        result = run("login", "anilist", "--token", "abc")

    assert result.exit_code == 0, result.output
    assert login.call_args.args[3] == "abc"


def test_login_failure_exits_non_zero(services):
    with patch("viu_media.cli.utils.tracker_login.login_anilist", return_value=False):
        assert run("login").exit_code == 1


def test_login_asks_where_to_track_first(services):
    tracking, _, _ = services
    tracking.enabled_trackers = []
    tracking.missing_logins.return_value = []
    with patch(
        "viu_media.cli.utils.tracker_login.choose_remote", return_value=False
    ) as choose:
        assert run("login").exit_code == 0
    choose.assert_called_once()


def test_logging_in_to_a_disabled_site_offers_to_sync_it(services):
    tracking, selector, _ = services
    tracking.is_enabled.return_value = False
    selector.confirm.return_value = True
    with patch(
        "viu_media.cli.utils.tracker_login.login_myanimelist", return_value=True
    ):
        result = run("login", "myanimelist", "--client-id", "cid")

    assert result.exit_code == 0, result.output
    tracking.set_mal_credentials.assert_called_once_with("cid", "")
    tracking.set_remote.assert_called_once_with("both")


def test_mode_and_logout(services):
    tracking, _, _ = services
    assert run("mode", "myanimelist").exit_code == 0
    tracking.set_remote.assert_called_once_with("myanimelist")

    assert run("logout").exit_code == 0
    assert [c.args[0] for c in tracking.logout.call_args_list] == [
        "anilist",
        "myanimelist",
    ]
    assert run("mode", "bogus").exit_code == 2


def test_tui_command_passes_the_images_flag():
    with patch("viu_media.cli.tui.run_tui") as run_tui:
        result = CliRunner().invoke(tui, ["--no-images"], obj=AppConfig())
    assert result.exit_code == 0, result.output
    assert run_tui.call_args.kwargs == {"images": False}


def test_anilist_opens_the_grid_when_configured():
    config = AppConfig()
    config.general.interface = "grid"
    with (
        patch("viu_media.cli.tui.run_tui") as run_tui,
        patch("viu_media.cli.interactive.session.session") as session,
    ):
        result = CliRunner().invoke(anilist, [], obj=config)

    assert result.exit_code == 0, result.output
    run_tui.assert_called_once_with(config)
    session.run.assert_not_called()
