"""A grid-based terminal UI for neoviu, built on Textual.

Textual and textual-image are optional (the ``tui`` extra), so nothing here is
imported until the user opens the grid interface.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...core.config import AppConfig

INSTALL_HINT = (
    "The grid interface needs the optional 'tui' extra. Install it with:\n"
    '  uv tool install "nviu[tui] @ git+https://github.com/NehemiahAklil/neoviu.git"\n'
    "or, from a checkout:  uv sync --extra tui"
)


def tui_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("textual") is not None


def run_tui(config: "AppConfig", images: bool = True) -> None:
    """Opens the grid TUI; raises ``click.ClickException`` if it is not installed."""
    import click

    if not tui_available():
        raise click.ClickException(INSTALL_HINT)

    from ..interactive.session import session
    from . import covers
    from .app import ViuApp

    covers.prepare_images(images)
    session.load_menus_from_folder("media")
    ViuApp(config).run()
