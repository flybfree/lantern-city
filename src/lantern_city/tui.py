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
import datetime
import json
from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual.app import App, ComposeResult, ScreenResultType
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Label, ListView, ListItem, RichLog, Static
from textual.worker import Worker, WorkerState

from lantern_city.app import LanternCityApp
from lantern_city.cli import _load_llm_config, _save_llm_config
from lantern_city.game_master import GameMaster
from lantern_city.llm_client import OpenAICompatibleConfig, OpenAICompatibleLLMClient
from lantern_city.models import CaseState, CityState, LocationState, PlayerProgressState

# Direct-command verbs whose output goes to the narrative pane (not info pane)
_NARRATIVE_INFO_COMMANDS = frozenset({"clues", "look", "overview"})

_WELCOME_TEXT = """\
[bold yellow]LANTERN CITY[/bold yellow]

[italic]The city runs on lanterns. Not for light — for memory. Each district burns \
a different kind, and what a lantern touches, it changes: testimony clarified or \
corrupted, evidence preserved or dissolved, truth bent toward whoever controls \
the flame.[/italic]

You are an investigator. Cases find you — a missing clerk, a ledger that shouldn't \
exist, a name spoken too carefully by someone who should not know it. You move \
through the districts, talk to the people who live under the lanterns, and try to \
separate what is solid from what the light has made uncertain.

[bold]── How to play ─────────────────────────────────────[/bold]

The Game Master understands natural language. Just describe what you want to do:

  [italic]"go to the old quarter"[/italic]
  [italic]"look around"[/italic]
  [italic]"talk to the shrine keeper about the missing clerk"[/italic]
  [italic]"examine the lantern post"[/italic]
  [italic]"what clues do I have so far?"[/italic]
  [italic]"where should I go next?"[/italic]  ← ask for a status update anytime

[bold]── Navigation ──────────────────────────────────────[/bold]

The city has six districts, each with its own lantern condition and locations. \
The panel on the right shows all districts — [dim]unexplored[/dim] ones are waiting. \
Within a district, locations hold objects, clues, and NPCs. Move between them \
freely; inspect locations to gather evidence.

[bold]── Investigation ────────────────────────────────────[/bold]

Clues have a [bold]reliability[/bold] rating shaped by the lanterns around them. \
A clue found under bright lanterns is solid. One found in a flickering or dim \
district may be uncertain or contradicted. NPCs can clarify testimony — or \
muddy it further. When you have enough solid evidence, you can attempt to \
resolve a case.

[bold]── Controls ─────────────────────────────────────────[/bold]

  [dim]Ctrl+G[/dim]  toggle GM / direct command mode
  [dim]Ctrl+R[/dim]  toggle map / player stats (reputation, leverage, attention)
  [dim]Ctrl+S[/dim]  configure LLM connection
  [dim]Ctrl+C[/dim]  quit
  [dim]↑ ↓[/dim]     cycle input history
  [dim]help[/dim]    show this screen again
"""

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

[dim]Ctrl+G — GM/CMD  |  Ctrl+R — map/stats  |  Ctrl+C — quit  |  ↑↓ history[/dim]"""


class TurnLogger:
    """Writes a rolling log of the last N turns to a JSON file beside the database.

    Log file: <database_stem>.log.json  (e.g. lantern-city.log.json)
    Each entry records timestamp, mode, input, and response.
    Only the most recent MAX_ENTRIES are kept.
    """

    MAX_ENTRIES = 5

    def __init__(self, database_path: str) -> None:
        self._path = Path(database_path).with_suffix(".log.json")

    def record(self, *, mode: str, player_input: str, response: str) -> None:
        entries: list[dict] = self._load()
        entries.append({
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "input": player_input,
            "response": response,
        })
        entries = entries[-self.MAX_ENTRIES:]
        try:
            self._path.write_text(
                json.dumps(entries, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return []


class CityPickerScreen(Screen[Path | None]):
    """Full-screen city selection shown when no --db argument is given."""

    CSS = """
    CityPickerScreen {
        align: center middle;
        background: $background;
    }
    #picker-box {
        width: 70;
        height: auto;
        max-height: 80vh;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #picker-title {
        text-align: center;
        color: $warning;
        padding-bottom: 1;
    }
    #picker-hint {
        color: $text-muted;
        padding-bottom: 1;
    }
    #city-list {
        height: auto;
        max-height: 20;
        border: solid $primary-darken-2;
        margin-bottom: 1;
    }
    #picker-buttons {
        height: 3;
        align: right middle;
    }
    #btn-open {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("escape", "quit", "Quit"),
        Binding("enter", "open_selected", "Open"),
    ]

    def __init__(self, cities: list[Path]) -> None:
        super().__init__()
        self._cities = cities

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Static("[bold yellow]LANTERN CITY[/bold yellow]", markup=True, id="picker-title")
            if self._cities:
                yield Static(
                    "Select a city file to open, or quit and run [bold]generate_city.py[/bold] to create a new one.",
                    markup=True,
                    id="picker-hint",
                )
                items = [
                    ListItem(Label(f"  {p.stem}  [dim]({p.name})[/dim]", markup=True), id=f"city-{i}")
                    for i, p in enumerate(self._cities)
                ]
                yield ListView(*items, id="city-list")
            else:
                yield Static(
                    "[yellow]No city files found.[/yellow]\n\n"
                    "Create one with:\n"
                    "  [dim]uv run python generate_city.py --url URL --model NAME[/dim]\n\n"
                    "Then relaunch the TUI.",
                    markup=True,
                    id="picker-hint",
                )
            with Horizontal(id="picker-buttons"):
                yield Button("Quit", variant="default", id="btn-quit")
                if self._cities:
                    yield Button("Open", variant="primary", id="btn-open")

    def on_mount(self) -> None:
        if self._cities:
            self.query_one("#city-list", ListView).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-quit":
            self.dismiss(None)
        elif event.button.id == "btn-open":
            self._open_selected()

    def action_open_selected(self) -> None:
        self._open_selected()

    def _open_selected(self) -> None:
        if not self._cities:
            return
        lv = self.query_one("#city-list", ListView)
        idx = lv.index or 0
        self.dismiss(self._cities[idx])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        if item_id.startswith("city-"):
            idx = int(item_id.removeprefix("city-"))
            self.dismiss(self._cities[idx])

    def action_quit(self) -> None:
        self.dismiss(None)


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
        Binding("ctrl+r", "toggle_info", "Toggle stats/map"),
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
        self._gm_mode: bool = True  # always start in GM mode; falls back to CMD if no LLM
        self._info_mode: str = "surroundings"  # "surroundings" or "stats"
        self._history: list[str] = []
        self._history_idx: int = 0
        self._visited_districts: set[str] = set()
        self._turn_log = TurnLogger(database_path)
        self._last_input: str = ""

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
        narrative.write(Text.from_markup(_WELCOME_TEXT))

        try:
            pos = self._game._load_position()
            if pos is not None:
                self._visited_districts.update(pos.visited_district_ids)
                if pos.district_id:
                    self._visited_districts.add(pos.district_id)
                narrative.write(Text.from_markup(
                    "[dim]Existing game detected. "
                    "Just tell me what you want to do.[/dim]\n"
                ))
            else:
                narrative.write(Text.from_markup(
                    "[dim]No active game. Type [bold]start[/bold] to begin.[/dim]\n"
                ))
        except Exception:
            pass

        self._refresh_surroundings()
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
        self._refresh_surroundings()
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

    def action_toggle_info(self) -> None:
        self._info_mode = "stats" if self._info_mode == "surroundings" else "surroundings"
        self._refresh_surroundings()

    def _apply_llm_config(self, url: str, model: str) -> None:
        """Instantiate a new LLM client + GM and enable GM mode."""
        llm_config = OpenAICompatibleConfig(base_url=url, model=model)
        self._game.llm_config = llm_config
        llm_client = OpenAICompatibleLLMClient(llm_config)
        self._gm = GameMaster(app=self._game, llm=llm_client)
        self._gm_mode = True
        self._refresh_surroundings()
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
        self._last_input = raw
        narrative = self.query_one("#narrative", RichLog)
        narrative.write(Text.from_markup(f"[dim]> {escape(raw)}[/dim]"))

        verb = raw.split()[0].lower() if raw.split() else ""

        # help / welcome — always local
        if verb == "help":
            narrative = self.query_one("#narrative", RichLog)
            narrative.write(Text.from_markup(_WELCOME_TEXT))
            return

        # clue list — always run the real clues command so the player sees actual clue text
        _raw_lower = raw.lower().strip()
        if verb == "clues" or any(phrase in _raw_lower for phrase in (
            "show my clues", "show clues", "list clues", "my clues",
            "what clues", "clues i have", "clues do i have",
        )):
            self.query_one("#cmd", Input).disabled = True
            self._update_status_raw("processing…")

            async def _run_clues() -> str:
                try:
                    return await asyncio.to_thread(self._game.run_command, "clues")
                except Exception as exc:
                    return f"⚠ {exc}"

            self.run_worker(_run_clues(), exclusive=True, name="cmd:clues")
            return

        # status update — ask the GM for a narrative recap, no game actions
        if verb in ("status", "update") or _raw_lower in (
            "where am i", "what's going on", "what is going on",
            "catch me up", "what do i know", "recap",
        ):
            if self._gm is not None:
                self.query_one("#cmd", Input).disabled = True
                self._update_status_raw("processing…")

                async def _run_status() -> str:
                    return await asyncio.to_thread(self._gm.status_update)

                self.run_worker(_run_status(), exclusive=True, name="gm")
                return
            # No GM — fall through to CMD handling

        self.query_one("#cmd", Input).disabled = True
        self._update_status_raw("processing…")

        # start — stream progress steps directly to the narrative log
        if verb == "start":
            concept_arg = raw.split(None, 1)[1] if len(raw.split(None, 1)) > 1 else None

            def _progress(msg: str) -> None:
                self.call_from_thread(
                    lambda m=msg: self.query_one("#narrative", RichLog).write(
                        Text.from_markup(f"[dim]{escape(m)}[/dim]")
                    )
                )

            async def _run_start() -> str:
                try:
                    return await asyncio.to_thread(
                        self._game.start_new_game, concept_arg, _progress
                    )
                except Exception as exc:
                    return f"\u26a0 {exc}"

            self.run_worker(_run_start(), exclusive=True, name="cmd:start")
            return

        if self._gm_mode and self._gm is not None:
            async def _run_gm() -> str:
                return await asyncio.to_thread(self._gm.process, raw)

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
                prose = event.worker.result  # type: ignore[assignment]
                self.query_one("#narrative", RichLog).write(escape(prose))
                self._turn_log.record(mode="GM", player_input=self._last_input, response=prose)
            else:
                result: str = event.worker.result  # type: ignore[assignment]
                self.query_one("#narrative", RichLog).write(escape(result))
                self._turn_log.record(mode="CMD", player_input=self._last_input, response=result)
        elif event.state == WorkerState.ERROR:
            err_text = f"Error: {event.worker.error}"
            self.query_one("#narrative", RichLog).write(Text(err_text, style="bold red"))
            self._turn_log.record(mode="ERR", player_input=self._last_input, response=err_text)

        cmd_input.disabled = False
        cmd_input.focus()
        self._refresh_status()
        self._refresh_surroundings()

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

    def _refresh_surroundings(self) -> None:
        if self._info_mode == "stats":
            panel = self._build_stats_panel()
        else:
            panel = self._build_surroundings_panel()
        self._update_info(panel, markup=True)

    def _build_surroundings_panel(self) -> str:
        try:
            pos = self._game._load_position()
            city = self._game._city()
        except Exception:
            return _HELP_TEXT

        if city is None or pos is None:
            return (
                "[dim]Ctrl+G — GM/CMD  |  Ctrl+R — map/stats  |  Ctrl+S — LLM[/dim]\n\n"
                "Type [bold]start[/bold] to begin a new game."
            )

        lines: list[str] = []

        # Sync visited districts from persisted store + current session
        self._visited_districts.update(pos.visited_district_ids)
        if pos.district_id:
            self._visited_districts.add(pos.district_id)

        # Mode indicator
        mode = "[bold green]GM[/bold green]" if self._gm_mode else "[bold yellow]CMD[/bold yellow]"
        lines.append(f"Mode: {mode}  [dim](Ctrl+G)[/dim]\n")

        # ── Current location detail ──────────────────────────────────
        if pos.district_id:
            district = self._game._district(pos.district_id)
            if district:
                lc = district.lantern_condition
                lantern_color = {
                    "bright": "yellow", "dim": "grey50", "flickering": "orange1",
                    "extinguished": "red", "altered": "magenta",
                }.get(lc, "white")
                lines.append(
                    f"[bold]▶ {escape(district.name)}[/bold]\n"
                    f"  [{lantern_color}]{escape(lc)} lanterns[/{lantern_color}]\n"
                )
                if district.visible_locations:
                    lines.append("[bold]Locations here:[/bold]")
                    for loc_id in district.visible_locations:
                        loc = self._game.store.load_object("LocationState", loc_id)
                        if not isinstance(loc, LocationState):
                            continue
                        is_here = loc_id == pos.location_id
                        marker = "[bold cyan]▶[/bold cyan]" if is_here else " "
                        lines.append(f"  {marker} [cyan]{escape(loc.name)}[/cyan]")
                        for nid in loc.known_npc_ids:
                            npc = self._game._npc(nid)
                            if npc:
                                lines.append(f"      · {escape(npc.name)}")
                    lines.append("")

        # ── All districts ────────────────────────────────────────────
        lines.append("[bold]City Districts:[/bold]")
        for did in city.district_ids:
            district = self._game._district(did)
            if not district:
                continue
            is_current = did == pos.district_id
            was_visited = did in self._visited_districts
            lc = district.lantern_condition
            lantern_color = {
                "bright": "yellow", "dim": "grey50", "flickering": "orange1",
                "extinguished": "red", "altered": "magenta",
            }.get(lc, "white")
            lantern_icon = {
                "bright": "◉", "dim": "◎", "flickering": "◌",
                "extinguished": "○", "altered": "◈",
            }.get(lc, "◎")

            if is_current:
                name_markup = f"[bold cyan]{escape(district.name)}[/bold cyan] [dim](here)[/dim]"
            elif was_visited:
                name_markup = f"{escape(district.name)} [dim](visited)[/dim]"
            else:
                name_markup = f"[dim]{escape(district.name)}[/dim] [dim]— unexplored[/dim]"

            lines.append(f"  [{lantern_color}]{lantern_icon}[/{lantern_color}] {name_markup}")
        lines.append("")

        # ── Active cases ─────────────────────────────────────────────
        active_cases = [
            self._game.store.load_object("CaseState", cid)
            for cid in city.active_case_ids
        ]
        active_cases = [c for c in active_cases if isinstance(c, CaseState)]
        if active_cases:
            lines.append("[bold]Cases:[/bold]")
            for case in active_cases:
                lines.append(f"  [yellow]{escape(case.title)}[/yellow]")
                lines.append(f"  [dim]{escape(case.status)}[/dim]")
            lines.append("")

        # ── Clues ────────────────────────────────────────────────────
        clue_count = len(pos.clue_ids)
        clue_color = "green" if clue_count > 0 else "dim"
        lines.append(f"[bold]Clues:[/bold] [{clue_color}]{clue_count} acquired[/{clue_color}]")
        if clue_count > 0:
            lines.append("  [dim]say 'show my clues'[/dim]")

        return "\n".join(lines)

    def _build_stats_panel(self) -> str:
        mode = "[bold green]GM[/bold green]" if self._gm_mode else "[bold yellow]CMD[/bold yellow]"
        lines: list[str] = [
            f"Mode: {mode}  [dim](Ctrl+G)[/dim]\n",
            "[bold yellow]Player Stats[/bold yellow]  [dim](Ctrl+R — back to map)[/dim]\n",
        ]

        try:
            progress_items = self._game.store.list_objects("PlayerProgressState")
            progress = progress_items[0] if progress_items else None
            if not isinstance(progress, PlayerProgressState):
                progress = None
        except Exception:
            progress = None

        try:
            cities = self._game.store.list_objects("CityState")
            city = cities[0] if cities else None
            if not isinstance(city, CityState):
                city = None
        except Exception:
            city = None

        if progress is None and city is None:
            lines.append("[dim]No game in progress.[/dim]")
            return "\n".join(lines)

        def _tier_color(tier: str) -> str:
            return {
                "Unknown": "dim", "Novice": "grey50", "Apprentice": "cyan",
                "Journeyman": "green", "Expert": "yellow", "Master": "bold yellow",
            }.get(tier, "white")

        if progress is not None:
            # Reputation
            rep = progress.reputation
            rc = _tier_color(rep.tier)
            lines.append(f"[bold]Reputation[/bold]")
            lines.append(f"  [{rc}]{rep.score:>3}  {escape(rep.tier)}[/{rc}]")
            lines.append("")

            # Leverage
            lev = progress.leverage
            lc = _tier_color(lev.tier)
            lines.append(f"[bold]Leverage[/bold]")
            lines.append(f"  [{lc}]{lev.score:>3}  {escape(lev.tier)}[/{lc}]")
            lines.append("")

            # Lantern Understanding
            lu = progress.lantern_understanding
            luc = _tier_color(lu.tier)
            lines.append(f"[bold]Lantern Understanding[/bold]")
            lines.append(f"  [{luc}]{lu.score:>3}  {escape(lu.tier)}[/{luc}]")
            lines.append("")

            # Access
            acc = progress.access
            ac = _tier_color(acc.tier)
            lines.append(f"[bold]Access[/bold]")
            lines.append(f"  [{ac}]{acc.score:>3}  {escape(acc.tier)}[/{ac}]")
            lines.append("")

        # Attention (player_presence_level from CityState)
        if city is not None:
            presence = city.player_presence_level
            if presence < 0.33:
                attn_label, attn_color, attn_icon = "Low", "green", "◎"
            elif presence < 0.67:
                attn_label, attn_color, attn_icon = "Medium", "yellow", "◉"
            else:
                attn_label, attn_color, attn_icon = "High", "red", "◈"
            pct = int(presence * 100)
            lines.append(f"[bold]Attention[/bold]")
            lines.append(
                f"  [{attn_color}]{attn_icon} {attn_label}[/{attn_color}]"
                f"  [dim]{pct}%[/dim]"
            )
            lines.append("")

            # City tension
            tension = city.global_tension
            if tension < 0.33:
                tens_label, tens_color = "Calm", "green"
            elif tension < 0.67:
                tens_label, tens_color = "Uneasy", "yellow"
            else:
                tens_label, tens_color = "Volatile", "red"
            tpct = int(tension * 100)
            lines.append(f"[bold]City Tension[/bold]")
            lines.append(
                f"  [{tens_color}]{tens_label}[/{tens_color}]"
                f"  [dim]{tpct}%[/dim]"
            )

        return "\n".join(lines)

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

def _scan_cities(directory: Path) -> list[Path]:
    """Return *.sqlite3 files in *directory*, newest-modified first."""
    return sorted(
        directory.glob("*.sqlite3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _run_city_picker(cities: list[Path]) -> Path | None:
    """Show the city picker screen and return the chosen path (or None to quit)."""

    class _PickerApp(App[Path | None]):
        def on_mount(self) -> None:
            self.push_screen(CityPickerScreen(cities), self.exit)

    return _PickerApp().run()


def main(argv: list[str] | None = None) -> int:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="lantern-city-tui")
    parser.add_argument("--db", dest="database_path", default=None,
                        help="Path to a city SQLite database. Omit to pick from available files.")
    parser.add_argument("--llm-url", dest="llm_url", default=None)
    parser.add_argument("--llm-model", dest="llm_model", default=None)
    args = parser.parse_args(argv)

    # Resolve database path — show picker if not specified
    if args.database_path is None:
        cities = _scan_cities(Path.cwd())
        if len(cities) == 1:
            # Only one city — open it automatically
            db_path = str(cities[0])
        else:
            chosen = _run_city_picker(cities)
            if chosen is None:
                return 0
            db_path = str(chosen)
    else:
        db_path = args.database_path

    if args.llm_url and args.llm_model:
        _save_llm_config(db_path, args.llm_url, args.llm_model)
        llm_config = OpenAICompatibleConfig(base_url=args.llm_url, model=args.llm_model)
    else:
        llm_config = _load_llm_config(db_path)

    game = LanternCityApp(Path(db_path), llm_config=llm_config)

    gm: GameMaster | None = None
    if llm_config is not None:
        llm_client = OpenAICompatibleLLMClient(llm_config)
        gm = GameMaster(app=game, llm=llm_client)

    LanternCityTUI(game, gm=gm, database_path=db_path).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
