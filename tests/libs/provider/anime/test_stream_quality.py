import pytest
from pydantic import ValidationError

from viu_media.core.config import AppConfig
from viu_media.libs.provider.anime.types import EpisodeStream


def test_preserves_nonstandard_upstream_video_height() -> None:
    stream = EpisodeStream.model_validate(
        {"link": "https://video.example/800.m3u8", "quality": "800"}
    )
    config = AppConfig.model_validate({"stream": {"quality": "800"}})
    assert stream.quality == "800"
    assert config.stream.quality == "800"
    assert AppConfig.model_validate(config.model_dump()).stream.quality == "800"


@pytest.mark.parametrize("quality", ["0", "-1", "best", "800p", ""])
def test_rejects_invalid_video_heights(quality: str) -> None:
    with pytest.raises(ValidationError):
        EpisodeStream.model_validate(
            {"link": "https://video.example/master.m3u8", "quality": quality}
        )
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"stream": {"quality": quality}})
