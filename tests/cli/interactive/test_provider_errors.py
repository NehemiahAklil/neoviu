from collections.abc import Iterator
from contextlib import nullcontext
from unittest.mock import MagicMock

import pytest

from viu_media.cli.interactive.menu.media.servers import servers
from viu_media.cli.interactive.session import Context, Menu, Session
from viu_media.cli.interactive.state import InternalDirective, MenuName, State
from viu_media.core.config import AppConfig
from viu_media.core.exceptions import ProviderAPIError
from viu_media.libs.media_api.types import MediaItem, MediaTitle
from viu_media.libs.provider.anime.types import Anime, AnimeEpisodes, Server


@pytest.mark.parametrize("at_root", [False, True])
def test_provider_failure_is_reported_without_crashing_the_session(
    at_root: bool,
) -> None:
    feedback = MagicMock()
    context = Context(config=AppConfig(), _feedback=feedback)
    session = Session()
    session._context = context
    root = State(menu_name=MenuName.MAIN)
    provider_state = State(menu_name=MenuName.PROVIDER_SEARCH)
    session._history = [root] if at_root else [root, provider_state]
    error = ProviderAPIError("hianime", 403, "Browser verification required")

    def unavailable(context: Context, state: State) -> InternalDirective:
        raise error

    def exit_menu(context: Context, state: State) -> InternalDirective:
        return InternalDirective.EXIT

    session._menus = {
        MenuName.MAIN: Menu(
            name=MenuName.MAIN, execute=unavailable if at_root else exit_menu
        ),
        MenuName.PROVIDER_SEARCH: Menu(
            name=MenuName.PROVIDER_SEARCH, execute=unavailable
        ),
    }
    session._run_main_loop()

    feedback.error.assert_called_once_with(str(error))
    assert session._history == [root]


def test_top_server_iteration_does_not_hide_provider_api_errors() -> None:
    error = ProviderAPIError("hianime", details="Upstream unavailable")

    def failing_streams() -> Iterator[Server]:
        yield from ()
        raise error

    provider = MagicMock()
    provider.episode_streams.return_value = failing_streams()
    feedback = MagicMock()
    feedback.progress.return_value = nullcontext()
    context = Context(
        config=AppConfig(),
        _provider=provider,
        _feedback=feedback,
        _selector=MagicMock(),
    )
    state = State.model_validate(
        {
            "menu_name": MenuName.SERVERS,
            "media_api": {
                "media_id": 20,
                "search_result": {
                    20: MediaItem(id=20, title=MediaTitle(english="Naruto"))
                },
            },
            "provider": {
                "anime": Anime(
                    id="naruto", title="Naruto", episodes=AnimeEpisodes(sub=["1"])
                ),
                "episode": "1",
            },
        }
    )
    with pytest.raises(ProviderAPIError, match="Upstream unavailable"):
        servers(context, state)
