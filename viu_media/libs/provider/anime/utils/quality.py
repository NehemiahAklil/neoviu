from collections.abc import Sequence

from ..types import EpisodeStream


def select_stream(links: Sequence[EpisodeStream], quality: str) -> EpisodeStream | None:
    for link in links:
        if link.quality == quality:
            return link
    return links[0] if links else None
