"""The neoviu grid TUI application."""

import logging
from typing import Callable, List, Optional

from textual.app import App, SuspendNotSupported
from textual.binding import Binding

from ...core.config import AppConfig
from ...libs.media_api.types import MediaItem
from ..interactive.session import Context
from . import covers
from .screens.detail import DetailScreen
from .screens.home import HomeScreen

logger = logging.getLogger(__name__)


class ViuApp(App):
    TITLE = "neoviu"
    SUB_TITLE = "Home"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=False, priority=True),
    ]

    def __init__(self, config: AppConfig, context: Optional[Context] = None) -> None:
        super().__init__()
        self.config = config
        self.ctx = context or Context(config)
        self.theme = "tokyo-night"

    def get_default_screen(self) -> HomeScreen:
        return HomeScreen()

    def on_unmount(self) -> None:
        covers.close()

    def open_media(
        self, item: MediaItem, on_change: Optional[Callable[[MediaItem], None]] = None
    ) -> None:
        def closed(result: Optional[MediaItem]) -> None:
            if result is not None and on_change is not None:
                on_change(result)

        self.push_screen(DetailScreen(item), closed)

    def play(self, item: MediaItem, episodes: bool = False) -> bool:
        """Hands the terminal to the classic stream flow for one anime.

        The provider search, episode and server menus run in the configured
        selector (fzf, rofi…), so progress tracking works exactly as in the
        classic menus. Returns True once the flow has run.
        """
        from ..interactive.session import session
        from ..interactive.state import MediaApiState, MenuName, State

        media_state = MediaApiState(search_result={item.id: item}, media_id=item.id)
        history: List[State] = [
            State(menu_name=MenuName.MEDIA_ACTIONS, media_api=media_state),
            State(menu_name=MenuName.PROVIDER_SEARCH, media_api=media_state),
        ]
        if episodes:
            self.ctx.switch.force_episodes_menu()
        return self._run_classic(
            lambda: session.run(
                self.config, history=history, context=self.ctx, embedded=True
            )
        )

    def run_classic(self) -> bool:
        """Opens the original fzf/rofi menus until the user exits them."""
        from ..interactive.session import session
        from ..interactive.state import MenuName, State

        return self._run_classic(
            lambda: session.run(
                self.config, history=[State(menu_name=MenuName.MAIN)], context=self.ctx
            )
        )

    def _run_classic(self, run: Callable[[], None]) -> bool:
        try:
            with self.suspend():
                try:
                    run()
                except KeyboardInterrupt:
                    pass
        except SuspendNotSupported:
            self.notify(
                "This terminal cannot hand control to the player menus.",
                title="Not supported",
                severity="error",
            )
            return False
        except Exception as e:
            logger.exception("The classic menu flow failed")
            self.notify(str(e), title="Playback failed", severity="error")
            return False
        self.refresh(layout=True)
        return True
