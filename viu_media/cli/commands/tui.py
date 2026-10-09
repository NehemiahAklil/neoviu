from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from ...core.config import AppConfig


@click.command(
    help=(
        "Open the grid interface: browse anime as cover grids, manage your "
        "AniList/MyAnimeList lists and keep your progress in sync. "
        "Requires the optional 'tui' extra."
    ),
    short_help="Open the grid interface",
)
@click.option(
    "--no-images",
    is_flag=True,
    help="Don't render cover images (useful over SSH or in slow terminals).",
)
@click.pass_obj
def tui(config: "AppConfig", no_images: bool):
    from ..tui import run_tui

    run_tui(config, images=not no_images)
