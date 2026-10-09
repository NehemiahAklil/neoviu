"""Small modal dialogs used by the grid TUI."""

from typing import Any, Callable, List, Optional, Tuple

from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

DIALOG_CSS = """
{name} {{
    align: center middle;
    background: $background 60%;
}}
{name} > Vertical {{
    width: 56;
    height: auto;
    max-height: 90%;
    padding: 1 2;
    border: thick $accent;
    background: $surface;
}}
{name} .dialog-title {{
    text-style: bold;
    margin-bottom: 1;
}}
{name} .dialog-message {{
    color: $text-muted;
    margin-bottom: 1;
}}
{name} .dialog-error {{
    color: $error;
    height: auto;
}}
{name} .dialog-buttons {{
    height: auto;
    margin-top: 1;
    align-horizontal: right;
}}
{name} .dialog-buttons Button {{
    margin-left: 1;
}}
"""


class ChoiceDialog(ModalScreen[Optional[str]]):
    DEFAULT_CSS = (
        DIALOG_CSS.format(name="ChoiceDialog")
        + """
    ChoiceDialog OptionList {
        height: auto;
        max-height: 16;
    }
    """
    )

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        title: str,
        options: List[Tuple[str, str]],
        current: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.dialog_title = title
        self.options = options
        self.current = current

    def compose(self):
        with Vertical():
            yield Static(self.dialog_title, classes="dialog-title", markup=False)
            yield OptionList(
                *[
                    Option(
                        f"● {label}" if value == self.current else f"  {label}",
                        id=value,
                    )
                    for value, label in self.options
                ]
            )

    def on_mount(self) -> None:
        option_list = self.query_one(OptionList)
        values = [value for value, _ in self.options]
        if self.current in values:
            option_list.highlighted = values.index(self.current)
        option_list.focus()

    @on(OptionList.OptionSelected)
    def _selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class InputDialog(ModalScreen[Optional[str]]):
    DEFAULT_CSS = DIALOG_CSS.format(name="InputDialog")

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        title: str,
        *,
        message: str = "",
        value: str = "",
        placeholder: str = "",
        password: bool = False,
        validate: Optional[Callable[[str], Optional[str]]] = None,
    ) -> None:
        super().__init__()
        self.dialog_title = title
        self.message = message
        self.value = value
        self.placeholder = placeholder
        self.password = password
        self.validate_value = validate

    def compose(self):
        with Vertical():
            yield Static(self.dialog_title, classes="dialog-title", markup=False)
            if self.message:
                yield Static(self.message, classes="dialog-message", markup=False)
            yield Input(
                value=self.value, placeholder=self.placeholder, password=self.password
            )
            yield Static("", classes="dialog-error", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    @on(Input.Submitted)
    def _submitted(self) -> None:
        self._accept()

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self._accept()

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)

    def _accept(self) -> None:
        value = self.query_one(Input).value.strip()
        error = self.validate_value(value) if self.validate_value else None
        if error:
            self.query_one(".dialog-error", Static).update(error)
            return
        self.dismiss(value)


class ConfirmDialog(ModalScreen[bool]):
    DEFAULT_CSS = DIALOG_CSS.format(name="ConfirmDialog")

    BINDINGS = [
        Binding("escape,n", "answer(False)", "No"),
        Binding("y", "answer(True)", "Yes"),
    ]

    def __init__(self, title: str, message: str = "", confirm: str = "Yes") -> None:
        super().__init__()
        self.dialog_title = title
        self.message = message
        self.confirm = confirm

    def compose(self):
        with Vertical():
            yield Static(self.dialog_title, classes="dialog-title", markup=False)
            if self.message:
                yield Static(self.message, classes="dialog-message", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="no")
                yield Button(self.confirm, id="yes", variant="error")

    def on_mount(self) -> None:
        self.query_one("#no", Button).focus()

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_answer(self, answer: Any) -> None:
        self.dismiss(bool(answer))


def score_validator(value: str) -> Optional[str]:
    try:
        score = float(value)
    except ValueError:
        return "Enter a number between 0 and 10."
    if not 0 <= score <= 10:
        return "Enter a number between 0 and 10."
    return None
