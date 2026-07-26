"""
Journal entry writer — Textual TUI.

Opens a warm, minimal writing environment:
  - Large free-form text area
  - Mood and energy sliders (1–5, keyboard-driven)
  - Tags input
  - Ctrl+S to save, Ctrl+Q / Escape to quit
"""

from __future__ import annotations

import locale
from datetime import date

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Input, Label, Static, TextArea

from ..models import Entry
from .theme import AMBER, SAGE, VIOLET, WRITER_CSS, dot_meter


class MoodEnergySelector(Static):
    """
    A keyboard-driven 1–5 selector.
    Press the digit key (1–5) to set the value.
    """

    BINDINGS = []  # handled at App level

    def __init__(self, name: str, value: int | None = None, color: str = SAGE, **kwargs):
        super().__init__(**kwargs)
        self._name = name
        self._value: int | None = value
        self._color = color

    @property
    def value(self) -> int | None:
        return self._value

    def set_value(self, v: int) -> None:
        self._value = max(1, min(5, v))
        self._refresh_display()

    def clear(self) -> None:
        self._value = None
        self._refresh_display()

    def _refresh_display(self) -> None:
        dots = dot_meter(self._value)
        label = ""
        if self._value is not None:
            label = f" {self._value}"
        self.update(f"[{self._color}]{dots}[/]{label}")


class WriterApp(App):
    """Main journal writer application."""

    CSS = WRITER_CSS

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=True, priority=True),
        Binding("ctrl+q", "quit_app", "Quit", show=True),
        Binding("escape", "quit_app", "Quit", show=False),
    ]

    def __init__(self, entry_date: date, existing: Entry | None = None) -> None:
        super().__init__()
        self.entry_date = entry_date
        self.existing = existing
        self._saved: bool = False
        self._result: Entry | None = None

        # Locale-aware date formatting
        try:
            locale.setlocale(locale.LC_TIME, "")
        except locale.Error:
            pass

    def compose(self) -> ComposeResult:
        date_str = self.entry_date.strftime("%A, %d %B %Y")

        yield Static(f"  speculae  ·  {date_str}", id="header")

        with Container(id="body"):
            yield TextArea(
                text=self.existing.content if self.existing else "",
                id="entry-area",
            )

            with Horizontal(id="meta-row"):
                yield Label("mood", id="mood-label")
                mood_val = self.existing.mood if self.existing else None
                self._mood = MoodEnergySelector(
                    "mood", value=mood_val, color=SAGE, id="mood-display"
                )
                # initialise display
                self._mood.update(
                    f"[{SAGE}]{dot_meter(mood_val)}[/]" + (f" {mood_val}" if mood_val else "")
                )
                yield self._mood

                yield Label("energy", id="energy-label")
                energy_val = self.existing.energy if self.existing else None
                self._energy = MoodEnergySelector(
                    "energy", value=energy_val, color=VIOLET, id="energy-display"
                )
                self._energy.update(
                    f"[{VIOLET}]{dot_meter(energy_val)}[/]" + (f" {energy_val}" if energy_val else "")
                )
                yield self._energy

            with Horizontal(id="tags-row"):
                yield Label("tags", id="tags-label")
                existing_tags = (
                    ", ".join(self.existing.tags) if self.existing and self.existing.tags else ""
                )
                yield Input(
                    value=existing_tags,
                    placeholder="comma-separated: work, gratitude, hard day",
                    id="tags-input",
                )

        yield Static(
            f"  [bold {AMBER}]ctrl+s[/] save   "
            f"[bold {AMBER}]1–5[/] set mood   "
            f"[bold {AMBER}]shift+1–5[/] set energy   "
            f"[bold {AMBER}]ctrl+q[/] quit",
            id="footer",
        )

    def on_mount(self) -> None:
        self.query_one("#entry-area", TextArea).focus()

    def on_key(self, event) -> None:
        """Intercept digit keys for mood/energy setting."""
        # 1–5 without modifier → mood
        # shift+1–5 → energy  (terminals may not send these, fallback: m+digit / e+digit)
        if event.character in "12345" and not event.ctrl and not event.meta:
            focused = self.focused
            # Only intercept if the text area is NOT focused — don't steal typing
            if focused and focused.id == "entry-area":
                return
            val = int(event.character)
            self._mood.set_value(val)
            event.stop()
        elif event.character in "!@#$%":  # shift+1–5 on US keyboard
            val = "!@#$%".index(event.character) + 1
            self._energy.set_value(val)
            event.stop()

    def action_save(self) -> None:
        content = self.query_one("#entry-area", TextArea).text.strip()
        tags_raw = self.query_one("#tags-input", Input).value.strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        self._result = Entry(
            date=self.entry_date,
            content=content,
            mood=self._mood.value,
            energy=self._energy.value,
            tags=tags,
            id=self.existing.id if self.existing else "",
            created_at=self.existing.created_at if self.existing else None,
        )
        self._saved = True
        self.exit(self._result)

    def action_quit_app(self) -> None:
        self.exit(None)

    @property
    def saved_entry(self) -> Entry | None:
        return self._result if self._saved else None


def run_writer(entry_date: date, existing: Entry | None = None) -> Entry | None:
    """
    Launch the writer TUI and return the saved Entry, or None if the user
    quit without saving.
    """
    app = WriterApp(entry_date=entry_date, existing=existing)
    result = app.run()
    # app.run() returns the value passed to exit()
    return result if isinstance(result, Entry) else None
