from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest

from viu_media.cli.commands.search import stream_anime
from viu_media.core.config import AppConfig
from viu_media.libs.provider.anime.types import (
    Anime,
    AnimeEpisodes,
    EpisodeStream,
    Server,
)


@pytest.mark.parametrize(
    ("preferred", "available", "selected"),
    [
        ("720", ["1080", "720"], "720"),
        ("800", ["1080", "800"], "800"),
        ("1080", ["800"], "800"),
    ],
)
def test_cli_plays_the_selected_quality_without_an_extra_prompt(
    preferred: str, available: list[str], selected: str
) -> None:
    config = AppConfig.model_validate({"stream": {"quality": preferred}})
    provider = MagicMock()
    provider.episode_streams.return_value = iter(
        [
            Server(
                name="test",
                links=[
                    EpisodeStream(
                        link=f"https://video.example/{quality}.m3u8", quality=quality
                    )
                    for quality in available
                ],
            )
        ]
    )
    selector = MagicMock()
    feedback = MagicMock()
    feedback.progress.return_value = nullcontext()
    anime = Anime(id="test", title="Naruto", episodes=AnimeEpisodes(sub=["1"]))

    with patch("viu_media.cli.service.player.service.PlayerService") as player:
        stream_anime(config, provider, selector, feedback, anime, "1", "Naruto")

    assert player.return_value.play.call_args.args[0].url == (
        f"https://video.example/{selected}.m3u8"
    )
    assert provider.episode_streams.call_args.args[0].quality == preferred
    selector.choose.assert_not_called()
