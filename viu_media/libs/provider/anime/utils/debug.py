import functools
import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import ParamSpec, Type, TypeVar, cast

from httpx import HTTPStatusError, RequestError

from .....core.exceptions import (
    ProviderAPIError,
    ProviderError,
    ProviderParsingError,
)

from ..base import BaseAnimeProvider

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


@contextmanager
def _provider_errors(provider_name: str) -> Iterator[None]:
    if os.environ.get("VIU_DEBUG"):
        yield
        return

    try:
        yield
    except ProviderError as error:
        logger.error("[%s]: %s", provider_name, error)
        raise
    except HTTPStatusError as error:
        status = error.response.status_code
        details = error.response.reason_phrase
        if status == 403:
            details = (
                "Access denied; the site may require browser verification. "
                "Try another provider."
            )
        provider_error = ProviderAPIError(provider_name, status, details)
        logger.error("%s", provider_error)
        raise provider_error from error
    except RequestError as error:
        provider_error = ProviderAPIError(
            provider_name,
            details=f"Unable to contact the provider ({type(error).__name__}).",
        )
        logger.error("%s", provider_error)
        raise provider_error from error
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
        parsing_error = ProviderParsingError(
            provider_name,
            f"Unable to parse the provider response ({type(error).__name__}).",
        )
        logger.error("%s", parsing_error)
        raise parsing_error from error


def _provider_iterator(iterator: Iterator[T], provider_name: str) -> Iterator[T]:
    with _provider_errors(provider_name):
        yield from iterator


def debug_provider(provider_function: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(provider_function)
    def _provider_function_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        provider_name = type(args[0]).__name__
        with _provider_errors(provider_name):
            result = provider_function(*args, **kwargs)
        # Stream generators make their requests during iteration, not construction.
        if isinstance(result, Iterator):
            return cast(R, _provider_iterator(result, provider_name))
        return result

    return _provider_function_wrapper


def test_anime_provider(AnimeProvider: Type[BaseAnimeProvider]):
    import shutil
    import subprocess

    from httpx import Client

    from .....core.constants import APP_ASCII_ART
    from .....core.utils.networking import random_user_agent
    from ..params import AnimeParams, EpisodeStreamsParams, SearchParams

    anime_provider = AnimeProvider(
        Client(headers={"User-Agent": random_user_agent(), **AnimeProvider.HEADERS})
    )
    print(APP_ASCII_ART.read_text(encoding="utf-8"))
    query = input("What anime would you like to stream: ")
    search_results = anime_provider.search(SearchParams(query=query))
    if not search_results:
        return
    for i, search_result in enumerate(search_results.results):
        print(f"{i + 1}: {search_result.title}")
    result = search_results.results[
        int(input(f"Select result (1-{len(search_results.results)}): ")) - 1
    ]
    anime = anime_provider.get(AnimeParams(id=result.id, query=query))

    if not anime:
        return
    translation_type = input("Preferred Translation Type: [dub,sub,raw]: ")
    for episode in getattr(anime.episodes, translation_type):
        print(episode)
    episode_number = input("What episode do you wish to watch: ")
    episode_streams = anime_provider.episode_streams(
        EpisodeStreamsParams(
            query=query,
            anime_id=anime.id,
            episode=episode_number,
            translation_type=translation_type,  # type:ignore
        )
    )

    if not episode_streams:
        return
    episode_streams = list(episode_streams)
    for i, stream in enumerate(episode_streams):
        print(f"{i + 1}: {stream.name}")
    stream = episode_streams[int(input("Select your preferred server: ")) - 1]
    for i, link in enumerate(stream.links):
        print(f"{i + 1}: {link.quality}")
    link = stream.links[int(input("Select your preferred quality: ")) - 1]
    if executable := shutil.which("mpv"):
        cmd = executable
    elif executable := shutil.which("xdg-open"):
        cmd = executable
    elif executable := shutil.which("open"):
        cmd = executable
    else:
        return

    print(
        "Now streaming: ",
        anime.title,
        "Episode: ",
        stream.episode_title if stream.episode_title else episode_number,
    )
    subprocess.run([cmd, link.link])
