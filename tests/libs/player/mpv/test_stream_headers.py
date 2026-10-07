import subprocess
from unittest.mock import patch

import pytest

from viu_media.core.config import MpvConfig
from viu_media.core.exceptions import ViuError
from viu_media.libs.player.mpv.player import MpvPlayer
from viu_media.libs.player.params import PlayerParams


def player_params() -> PlayerParams:
    return PlayerParams(
        url="https://video.example/master.m3u8",
        title="Naruto",
        query="Naruto",
        episode="1",
        headers={
            "Referer": "https://zokoanime.video/",
            "User-Agent": "Mozilla/5.0 (KHTML, like Gecko)",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )


def test_http_header_values_with_commas_remain_single_list_items() -> None:
    player = MpvPlayer(MpvConfig(args=""))
    options = player._create_mpv_cli_options(player_params())
    assert options[:4] == [
        "--http-header-fields-clr",
        "--http-header-fields-append=Referer:https://zokoanime.video/",
        "--http-header-fields-append=User-Agent:Mozilla/5.0 (KHTML, like Gecko)",
        "--http-header-fields-append=Accept-Language:en-US,en;q=0.5",
    ]


def test_mpv_failure_is_not_returned_as_successful_playback() -> None:
    player = MpvPlayer(MpvConfig(args=""))
    player.executable = "mpv"
    result = subprocess.CompletedProcess(
        args=["mpv"], returncode=2, stdout="", stderr="HTTP error 400 Bad Request"
    )
    with patch("viu_media.libs.player.mpv.player.subprocess.run", return_value=result):
        with pytest.raises(ViuError, match="MPV.*2"):
            player._stream_on_desktop_with_subprocess(player_params())


def test_successful_mpv_playback_retains_progress_parsing() -> None:
    player = MpvPlayer(MpvConfig(args=""))
    player.executable = "mpv"
    result = subprocess.CompletedProcess(
        args=["mpv"],
        returncode=0,
        stdout="AV: 00:00:10 / 00:24:00 (1%)",
        stderr="",
    )
    with patch("viu_media.libs.player.mpv.player.subprocess.run", return_value=result):
        playback = player._stream_on_desktop_with_subprocess(player_params())
    assert playback.episode == "1"
    assert playback.stop_time == "00:00:10"
    assert playback.total_time == "00:24:00"
