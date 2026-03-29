"""Textual TUI for Lantern City.

Four-pane layout:
  - Status bar (top, 1 line): district / location / clue count / mode indicator
  - Narrative pane (left 2/3): scrolling game output or GM prose
  - Info pane (right 1/3): clues, look output, help reference
  - Input bar (bottom): command or natural-language entry

Modes:
  GM mode  (Ctrl+G to toggle on/off) — natural language routed through the LLM
            Game Master: interpret → execute → narrate as atmospheric prose.
            Available when an LLM is configured.
  CMD mode — direct commands (start, enter, go, inspect, talk, …)

Launch:
    uv run lantern-city-tui [--db PATH] [--llm-url URL --llm-model MODEL]
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual.app import App, ComposeResult, ScreenResultType
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RichLog, Static
from textual.worker import Worker, WorkerState

from lantern_city.app import LanternCityApp
from lantern_city.cli import _load_llm_config, _save_llm_config
from lantern_city.game_master import GameMaster
from lantern_city.llm_client import OpenAICompatibleConfig, OpenAICompatibleLLMClient

# Direct-command verbs whose output replaces the info pane
_INFO_COMMANDS = frozenset({"clues", "look", "overview", "help"})

_HELP_TEXT = """\
[bold yellow]Commands[/bold yellow]  [dim](Ctrl+S — LLM settings)[/dim]

  [bold]start[/bold]                        begin a new game
  [bold]overview[/bold]                     city-level summary
  [bold]look[/bold] [dim][district_id][/dim]          district detail
  [bold]enter[/bold] [dim]<district_id>[/dim]         travel to a district
  [bold]go[/bold] [dim]<location_id>[/dim]            move to a location
  [bold]inspect[/bold] [dim]<location_id>[/dim]       examine a location
  [bold]talk[/bold] [dim]<npc_id> <text>[/dim]        speak with an NPC
  [bold]case[/bold] [dim]<case_id>[/dim]              attempt to resolve a case
  [bold]clues[/bold]                        view acquired clues
  [bold]help[/bold]                         show this panel

[dim]Ctrl+G — toggle GM / CMD mode  |  Ctrl+C — quit  |  ↑↓ command history[/dim]"""

_GM_HINT = """\
[bold yellow]GM Mode[/bold yellow]  [dim](Ctrl+G to switch to direct commands)[/dim]

Type naturally — the Game Master will interpret your intent,
take the appropriate actions, and narrate the results as prose.

[dim]Examples:[/dim]
  [italic]look around the district[/italic]
  [italic]ask the shrine keeper about the missing clerk[/italic]
  [italic]examine the lantern post[/italic]
  [italic]what cases am I working on?[/italic]
  [italic]show me my clues[/italic]
"""


class SettingsScreen(ModalScreen[tuple[str, str] | None]):
    """Modal overlay for configuring the LLM connection."""

    CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #settings-dialog Label {
        margin-top: 1;
        color: $text-muted;
    }
    #settings-dialog Input {
        margin-bottom: 0;
    }
    #settings-buttons {
        height: 3;
        margin-top: 1;
        align: right middle;
    }
    #btn-save {
        margin-left: 1;
    }
    """

    def __init__(self, current_url: str = "", current_model: str = "") -> None:
        super().__init__()
        self._current_url = current_url
        self._current_model = current_model

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Static("[bold yellow]LLM Settings[/bold yellow]", markup=True)
            yield Label("Base URL  (e.g. http://localhost:11434)")
            yield Input(value=self._current_url, placeholder="http://host/v1", id="inp-url")
            yield Label("Model name")
            yield Input(value=self._current_model, placeholder="gpt-4o-mini", id="inp-model")
            with Horizontal(id="settings-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Save", variant="primary", id="btn-save")

    def on_mount(self) -> None:
        self.query_one("#inp-url", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        url = self.query_one("#inp-url", Input).value.strip()
        model = self.query_one("#inp-model", Input).value.strip()
        if url and model:
            self.dismiss((url, model))
        else:
            # Highlight missing fields
            if not url:
                self.query_one("#inp-url", Input).focus()
            else:
                self.query_one("#inp-model", Input).focus()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class LanternCityTUI(App[None]):
    """Lantern City text user interface."""

    CSS = """
    Screen { layout: vertical; }

    #status-bar {
        dock: top;
        height: 1;
        background: $primary-darken-3;
        color: $text-muted;
        padding: 0 1;
    }

    #content {
        height: 1fr;
        layout: horizontal;
    }

    #narrative {
        width: 2fr;
        border-right: solid $primary-darken-2;
        padding: 0 1;
    }

    #info-scroll {
        width: 1fr;
        background: $surface-darken-1;
    }

    #info-pane {
        padding: 1 1;
    }

    #input-bar {
        dock: bottom;
        height: 3;
        background: $surface;
        border-top: solid $primary-darken-2;
        layout: horizontal;
        padding: 0 1;
        align: left middle;
    }

    #cmd {
        width: 1fr;
        border: none;
        background: transparent;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+g", "toggle_gm", "Toggle GM mode"),
        Binding("ctrl+s", "settings", "LLM settings"),
    ]

    def __init__(
        self,
        game: LanternCityApp,
        gm: GameMaster | None = None,
        database_path: str = "lantern-city.sqlite3",
    ) -> None:
        super().__init__()
        self._game = game
        self._gm = gm
        self._database_path = database_path
        self._gm_mode: bool = gm is not None  # default on when LLM is available
        self._history: list[str] = []
        self._history_idx: int = 0

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("Lantern City", id="status-bar")
        with Horizontal(id="content"):
            yield RichLog(highlight=True, markup=True, wrap=True, id="narrative")
            with ScrollableContainer(id="info-scroll"):
                yield Static("", markup=True, id="info-pane")
        with Horizontal(id="input-bar"):
            yield Input(placeholder="enter command…", id="cmd")

    def on_mount(self) -> None:
        narrative = self.query_one("#narrative", RichLog)
        narrative.write(Text.from_markup(
            "[bold yellow]Lantern City[/bold yellow]  — a text investigation game\n"
        ))

        try:
            pos = self._game._load_position()
            if pos is not None:
                narrative.write(Text.from_markup(
                    "[dim]Existing game detected. "
                    "Type [bold]overview[/bold] or [bold]look[/bold] to review state.[/dim]\n"
                ))
            else:
                narrative.write(Text.from_markup(
                    "[dim]No active game. Type [bold]start[/bold] to begin.[/dim]\n"
                ))
        except Exception:
            pass

        self._update_info(_GM_HINT if self._gm_mode else _HELP_TEXT, markup=True)
        self._refresh_status()
        self._update_input_placeholder()
        self.query_one("#cmd", Input).focus()

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        event.input.clear()
        if not command:
            return
        self._history.append(command)
        self._history_idx = len(self._history)
        self._dispatch(command)

    def on_key(self, event) -> None:
        """Up/down arrows cycle command history when input is focused."""
        cmd_input = self.query_one("#cmd", Input)
        if not cmd_input.has_focus:
            return
        if event.key == "up":
            event.prevent_default()
            if self._history:
                self._history_idx = max(0, self._history_idx - 1)
                cmd_input.value = self._history[self._history_idx]
                cmd_input.cursor_position = len(cmd_input.value)
        elif event.key == "down":
            event.prevent_default()
            self._history_idx = min(len(self._history), self._history_idx + 1)
            cmd_input.value = (
                self._history[self._history_idx]
                if self._history_idx < len(self._history)
                else ""
            )
            cmd_input.cursor_position = len(cmd_input.value)

    # ------------------------------------------------------------------
    # Mode toggle
    # ------------------------------------------------------------------

    def action_toggle_gm(self) -> None:
        if self._gm is None:
            narrative = self.query_one("#narrative", RichLog)
            narrative.write(Text.from_markup(
                "[yellow]GM mode requires an LLM config (--llm-url / --llm-model).[/yellow]"
            ))
            return
        self._gm_mode = not self._gm_mode
        self._update_info(_GM_HINT if self._gm_mode else _HELP_TEXT, markup=True)
        self._refresh_status()
        self._update_input_placeholder()
        narrative = self.query_one("#narrative", RichLog)
        mode_label = "GM mode" if self._gm_mode else "command mode"
        narrative.write(Text.from_markup(f"[dim]Switched to {mode_label}.[/dim]"))

    def action_settings(self) -> None:
        current = _load_llm_config(self._database_path)
        url = current.base_url if current else ""
        model = current.model if current else ""

        def _on_close(result: tuple[str, str] | None) -> None:
            if result is None:
                return
            url, model = result
            _save_llm_config(self._database_path, url, model)
            self._apply_llm_config(url, model)

        self.push_screen(SettingsScreen(url, model), _on_close)

    def _apply_llm_config(self, url: str, model: str) -> None:
        """Instantiate a new LLM client + GM and enable GM mode."""
        llm_config = OpenAICompatibleConfig(base_url=url, model=model)
        self._game.llm_config = llm_config
        llm_client = OpenAICompatibleLLMClient(llm_config)
        self._gm = GameMaster(app=self._game, llm=llm_client)
        self._gm_mode = True
        self._update_info(_GM_HINT, markup=True)
        self._refresh_status()
        self._update_input_placeholder()
        narrative = self.query_one("#narrative", RichLog)
        narrative.write(Text.from_markup(
            f"[green]LLM configured:[/green] {escape(url)}  model: {escape(model)}\n"
            "[dim]GM mode activated.[/dim]"
        ))

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, raw: str) -> None:
        narrative = self.query_one("#narrative", RichLog)
        narrative.write(Text.from_markup(f"[dim]> {escape(raw)}[/dim]"))

        verb = raw.split()[0].lower() if raw.split() else ""

        # help is always local
        if verb == "help":
            self._update_info(_HELP_TEXT, markup=True)
            return

        self.query_one("#cmd", Input).disabled = True
        self._update_status_raw("processing…")

        if self._gm_mode and self._gm is not None:
            async def _run_gm() -> tuple[str, str]:
                result = await asyncio.to_thread(self._gm.process, raw)
                clues = await asyncio.to_thread(self._game.clues)
                return result, clues

            self.run_worker(_run_gm(), exclusive=True, name="gm")
        else:
            async def _run_cmd() -> str:
                try:
                    return await asyncio.to_thread(self._game.run_command, raw)
                except Exception as exc:
                    return f"\u26a0 {exc}"

            self.run_worker(_run_cmd(), exclusive=True, name=f"cmd:{verb}")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        name = event.worker.name or ""
        if not (name == "gm" or name.startswith("cmd:")):
            return
        if event.state not in (WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED):
            return

        cmd_input = self.query_one("#cmd", Input)

        if event.state == WorkerState.SUCCESS:
            if name == "gm":
                prose, clues_text = event.worker.result  # type: ignore[misc]
                narrative = self.query_one("#narrative", RichLog)
                narrative.write(escape(prose))
                # Auto-refresh info pane with current clues after each GM turn
                self._update_info(escape(clues_text), markup=True)
            else:
                verb = name[4:]  # strip "cmd:"
                result: str = event.worker.result  # type: ignore[assignment]
                self._handle_cmd_result(verb, result)
        elif event.state == WorkerState.ERROR:
            narrative = self.query_one("#narrative", RichLog)
            narrative.write(Text(f"Error: {event.worker.error}", style="bold red"))

        cmd_input.disabled = False
        cmd_input.focus()
        self._refresh_status()

    def _handle_cmd_result(self, verb: str, result: str) -> None:
        if verb in _INFO_COMMANDS:
            self._update_info(escape(result), markup=True)
        else:
            self.query_one("#narrative", RichLog).write(escape(result))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_info(self, text: str, *, markup: bool = False) -> None:
        pane = self.query_one("#info-pane", Static)
        if markup:
            pane.update(text)
        else:
            pane.update(Text(text))

    def _update_status_raw(self, text: str) -> None:
        self.query_one("#status-bar", Static).update(text)

    def _update_input_placeholder(self) -> None:
        cmd = self.query_one("#cmd", Input)
        if self._gm_mode:
            cmd.placeholder = "What do you do?"
        else:
            cmd.placeholder = "enter command…"

    def _refresh_status(self) -> None:
        mode = "[GM]" if self._gm_mode else "[CMD]"
        try:
            pos = self._game._load_position()
            if pos is None:
                self._update_status_raw(f"Lantern City  {mode}  |  no active game  |  type 'start'")
                return
            parts: list[str] = [f"Lantern City  {mode}"]
            if pos.district_id:
                parts.append(f"District: {pos.district_id}")
            if pos.location_id:
                parts.append(f"Location: {pos.location_id}")
            parts.append(f"Clues: {len(pos.clue_ids)}")
            self._update_status_raw("  |  ".join(parts))
        except Exception:
            self._update_status_raw(f"Lantern City  {mode}")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="lantern-city-tui")
    parser.add_argument("--db", dest="database_path", default="lantern-city.sqlite3")
    parser.add_argument("--llm-url", dest="llm_url", default=None)
    parser.add_argument("--llm-model", dest="llm_model", default=None)
    args = parser.parse_args(argv)

    if args.llm_url and args.llm_model:
        _save_llm_config(args.database_path, args.llm_url, args.llm_model)
        llm_config = OpenAICompatibleConfig(base_url=args.llm_url, model=args.llm_model)
    else:
        llm_config = _load_llm_config(args.database_path)

    game = LanternCityApp(Path(args.database_path), llm_config=llm_config)

    gm: GameMaster | None = None
    if llm_config is not None:
        llm_client = OpenAICompatibleLLMClient(llm_config)
        gm = GameMaster(app=game, llm=llm_client)

    LanternCityTUI(game, gm=gm, database_path=args.database_path).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
