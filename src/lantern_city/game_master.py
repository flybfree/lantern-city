"""LLM Game Master for Lantern City.

Two-phase pipeline per player turn:

  1. Interpret — natural language → structured game commands (JSON)
  2. Execute   — commands run through LanternCityApp unchanged
  3. Narrate   — game results → atmospheric prose (free text)

The existing game engine is untouched; the GM is a translation layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from lantern_city.app import LanternCityApp
from lantern_city.llm_client import OpenAICompatibleLLMClient
from lantern_city.log import get_logger
from lantern_city.models import CaseState, LocationState

log = get_logger(__name__)


_INTERPRET_SYSTEM = """\
You are the command interpreter for Lantern City, a noir text investigation game.
Translate the player's natural language input into structured game commands.

Available commands (use exact syntax):
  start                       — begin a new game with a generated city (only if no game is active)
  start <concept>             — begin a new game; concept guides the generated city
  overview                    — city-level summary (no arguments)
  look                        — show detail for the CURRENT DISTRICT (no arguments)
  look <district_id>          — show detail for a named district (use a district_id only)
  enter <district_id>         — travel to a district (use a district_id only)
  go <location_id>            — move to a specific location inside the current district
  inspect <location_id>       — examine a location and gather clues
  talk <npc_id> <prompt>      — speak with an NPC; preserve player's words as the prompt
  clues                       — list acquired clues
  case <case_id>              — attempt to resolve a case

ID rules — CRITICAL:
- district_id values start with "district_" (e.g. district_old_quarter)
- location_id values start with "location_" (e.g. location_shrine_lane)
- npc_id values start with "npc_" (e.g. npc_shrine_keeper)
- NEVER pass a location_id to "look" or "enter" — those only accept district_ids
- NEVER pass a district_id to "go" or "inspect" — those only accept location_ids
- Use ONLY IDs that appear verbatim in the context block below

Output rules — CRITICAL:
- The "commands" array contains 0–3 elements. Each element is ONE complete command string.
- A command string includes the verb AND all arguments in a single string.
  CORRECT:   ["enter district_golden_pagoda"]
  WRONG:     ["enter", "district_golden_pagoda"]
- For talk commands, carry the player's own phrasing into the prompt argument.
- If the player asks a question answerable from context (e.g. "what cases do I have?"),
  output 0 commands — the narrator will answer from context alone.
- If the requested action is impossible, output 0 commands.
- Return JSON matching the schema exactly. No extra keys. No reasoning text.
"""

_NARRATE_SYSTEM = """\
You are the narrator for Lantern City, a noir investigative text game set in a city \
where lanterns control memory and truth. The city is oppressive, atmospheric, morally grey.

OUTPUT RULES — follow exactly:
- Write ONLY 2–5 sentences of finished prose. Nothing else.
- Do NOT include any reasoning, analysis, thinking steps, headers, bullet points, or \
self-commentary. Begin immediately with the narrative sentence.
- Use second-person ("You…").
- Ground every detail in the game data provided — never invent clues, NPCs, or facts.
- Noir tone: spare, evocative, foreboding. No exclamation marks. No purple prose.
- If an action failed, narrate it naturally without breaking immersion.
- End on atmosphere, not resolution.
"""

# Number of past turns to keep in memory
_MAX_HISTORY = 8
# How many past turns to include in each LLM prompt
_HISTORY_WINDOW = 3


@dataclass
class GameMaster:
    """Translates natural language player input into game commands and prose narrative."""

    app: LanternCityApp
    llm: OpenAICompatibleLLMClient
    _history: list[dict[str, str]] = field(default_factory=list, init=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, player_input: str) -> str:
        """Full GM turn: interpret → execute → narrate. Returns prose narrative."""
        log.debug("GM.process input=%r", player_input)
        context = self._build_context()
        commands = self._interpret(player_input, context)
        log.debug("GM.interpret commands=%r", commands)
        results = self._execute(commands)
        log.debug("GM.execute results=%r", results)
        narrative = self._narrate(player_input, commands, results, context)
        log.debug("GM.narrate prose=%r", narrative[:120])
        self._append_history(player_input, narrative)
        return narrative

    def status_update(self) -> str:
        """Return a GM-narrated summary of the player's current situation.

        No commands are executed — this is a pure narrative recap grounded in
        current game state and recent history.
        """
        context = self._build_context()
        system = (
            _NARRATE_SYSTEM
            + "\nWrite a 3–5 sentence recap of where the player is, what they have "
            "learned so far, and what avenues remain open. Ground every detail in the "
            "game state. Do not invent new facts. End with an atmospheric suggestion "
            "of what to do next, without being prescriptive."
        )
        history_block = self._history_block()
        user_content = (
            f"{history_block}"
            f"Current game state:\n{context}\n\n"
            "The player has asked for a status update. "
            "Summarise where things stand in the investigation."
        )
        schema = {
            "type": "object",
            "properties": {
                "narrative": {
                    "type": "string",
                    "description": "3–5 sentence noir prose recap. No reasoning or headers.",
                }
            },
            "required": ["narrative"],
            "additionalProperties": False,
        }
        try:
            result = self.llm.generate_json(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.65,
                max_tokens=500,
                schema=schema,
            )
            prose = result.get("narrative", "")
            if prose:
                return _strip_thinking(str(prose))
        except Exception:
            pass
        return context

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _build_context(self) -> str:
        lines: list[str] = []
        try:
            pos = self.app._load_position()
            city = self.app._city()
        except Exception:
            return "No active game."

        if city is None:
            return "No active game. The player must type 'start' to begin."

        current_district_id = pos.district_id if pos is not None else None

        if current_district_id:
            district = self.app._district(current_district_id)
            if district is not None:
                lines.append(
                    f"Current district: {district.name} ({current_district_id})"
                    f"  lanterns: {district.lantern_condition}"
                )
            else:
                lines.append(f"Current district: ({current_district_id})")

            if pos is not None and pos.location_id:
                loc = self.app.store.load_object("LocationState", pos.location_id)
                if isinstance(loc, LocationState):
                    lines.append(f"Current location: {loc.name} ({pos.location_id})")
            else:
                lines.append("Current location: — (not yet moved to a specific location)")

            # Locations available in the current district
            if district is not None and district.visible_locations:
                lines.append("\nLocations in this district:")
                for loc_id in district.visible_locations:
                    loc = self.app.store.load_object("LocationState", loc_id)
                    if isinstance(loc, LocationState):
                        npc_parts: list[str] = []
                        for nid in loc.known_npc_ids:
                            npc = self.app._npc(nid)
                            if npc:
                                npc_parts.append(f"{npc.name} ({nid})")
                        npc_str = ", ".join(npc_parts) if npc_parts else "—"
                        lines.append(f"  {loc.name} ({loc_id})  NPCs: {npc_str}")
        else:
            lines.append("Current district: — (player has not entered a district yet)")

        # Always list ALL districts so the GM can generate enter commands for any of them
        lines.append("\nAll city districts (use district_id with 'enter' command):")
        for did in city.district_ids:
            district = self.app._district(did)
            if district is not None:
                marker = " [CURRENT]" if did == current_district_id else ""
                lines.append(
                    f"  {district.name} ({did})"
                    f"  lanterns: {district.lantern_condition}{marker}"
                )

        # Cases
        active_cases = [
            self.app.store.load_object("CaseState", cid)
            for cid in city.active_case_ids
        ]
        active_cases = [c for c in active_cases if isinstance(c, CaseState)]
        acquired_clue_ids: set[str] = set(pos.clue_ids) if pos is not None else set()
        if active_cases:
            lines.append("\nActive cases:")
            for case in active_cases:
                lines.append(f"  {case.title} ({case.id})  [{case.status}]")
                lines.append(f"    Objective: {case.objective_summary}")
                if case.involved_district_ids:
                    lines.append(f"    Involved districts: {', '.join(case.involved_district_ids)}")

                # List locations in involved districts that have uninvestigated case clues
                uninvestigated: list[str] = []
                case_clue_ids = set(case.known_clue_ids)
                for did in case.involved_district_ids:
                    district = self.app._district(did)
                    if district is None:
                        continue
                    for loc_id in district.visible_locations:
                        loc = self.app.store.load_object("LocationState", loc_id)
                        if not isinstance(loc, LocationState):
                            continue
                        remaining = [c for c in loc.clue_ids if c in case_clue_ids and c not in acquired_clue_ids]
                        if remaining:
                            uninvestigated.append(f"{loc.name} ({loc_id})")
                if uninvestigated:
                    lines.append(
                        f"    Locations with uninvestigated clues: {', '.join(uninvestigated)}"
                    )

                # Key NPCs involved in this case
                key_npcs: list[str] = []
                for npc_id in case.involved_npc_ids:
                    npc = self.app._npc(npc_id)
                    if npc:
                        key_npcs.append(f"{npc.name} ({npc_id})")
                if key_npcs:
                    lines.append(f"    Key NPCs: {', '.join(key_npcs)}")
        else:
            lines.append("\nActive cases: none")

        # Hook NPC signal — if the player is currently talking to an NPC who introduces a latent case,
        # tell the GM so it can weave the case hook naturally into the conversation.
        current_npc_ids: list[str] = pos.npc_ids if pos is not None else []
        if current_npc_ids:
            all_cases = [
                self.app.store.load_object("CaseState", cid)
                for cid in city.active_case_ids
            ]
            for case in all_cases:
                if not isinstance(case, CaseState):
                    continue
                if case.status != "latent":
                    continue
                if case.hook_npc_id and case.hook_npc_id in current_npc_ids:
                    hook_npc = self.app._npc(case.hook_npc_id)
                    npc_name = hook_npc.name if hook_npc else case.hook_npc_id
                    lines.append(
                        f"\n[GM NOTE] {npc_name} is the person who will bring the case "
                        f'"{case.title}" to the player\'s attention. '
                        f"If the conversation opens naturally, have them say or imply: "
                        f"{case.discovery_hook}"
                    )

        # Clue count
        clue_count = len(pos.clue_ids) if pos is not None else 0
        lines.append(f"\nAcquired clues: {clue_count}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Phase 1: interpret
    # ------------------------------------------------------------------

    def _interpret(self, player_input: str, context: str) -> list[str]:
        schema = {
            "type": "object",
            "properties": {
                "commands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "0–3 command strings to execute",
                },
                "understood_as": {
                    "type": "string",
                    "description": "One-line summary of what the player intends",
                },
            },
            "required": ["commands", "understood_as"],
            "additionalProperties": False,
        }
        user_content = (
            f"{self._history_block()}"
            f"Current game state:\n{context}\n\n"
            f"Player input: {player_input}"
        )
        try:
            result = self.llm.generate_json(
                messages=[
                    {"role": "system", "content": _INTERPRET_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                max_tokens=300,
                schema=schema,
            )
            commands = result.get("commands", [])
            if isinstance(commands, list):
                raw = [str(c).strip() for c in commands if str(c).strip()]
                return _rejoin_split_commands(raw)
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------
    # Phase 2: execute
    # ------------------------------------------------------------------

    def _execute(self, commands: list[str]) -> list[str]:
        results: list[str] = []
        for cmd in commands:
            try:
                results.append(self.app.run_command(cmd))
            except Exception as exc:
                results.append(f"[action not possible: {exc}]")
        return results

    # ------------------------------------------------------------------
    # Phase 3: narrate
    # ------------------------------------------------------------------

    def _narrate(
        self,
        player_input: str,
        commands: list[str],
        results: list[str],
        context: str,
    ) -> str:
        if commands and results:
            pairs = "\n".join(
                f"  > {cmd}\n  {res}\n" for cmd, res in zip(commands, results)
            )
            events_block = f"\nGame events this turn:\n{pairs}"
        else:
            events_block = "\n(No game actions executed — answer from context and history.)"

        user_content = (
            f"{self._history_block()}"
            f"Current game state:\n{context}\n"
            f"{events_block}\n\n"
            f'Player said: "{player_input}"\n\n'
            "Write a brief atmospheric narrative response (2–5 sentences)."
        )
        schema = {
            "type": "object",
            "properties": {
                "narrative": {
                    "type": "string",
                    "description": "2–5 sentences of finished noir prose. No reasoning, no headers.",
                }
            },
            "required": ["narrative"],
            "additionalProperties": False,
        }
        try:
            result = self.llm.generate_json(
                messages=[
                    {"role": "system", "content": _NARRATE_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.75,
                max_tokens=500,
                schema=schema,
            )
            prose = result.get("narrative", "")
            if prose:
                return _strip_thinking(str(prose))
        except Exception:
            pass
        # Fallback: return raw game results when narration fails
        if results:
            return "\n\n".join(results)
        return "(The city offers no response.)"

    # ------------------------------------------------------------------
    # History helpers
    # ------------------------------------------------------------------

    def _append_history(self, player_input: str, narrative: str) -> None:
        self._history.append({"player": player_input, "gm": narrative})
        if len(self._history) > _MAX_HISTORY:
            self._history = self._history[-_MAX_HISTORY:]

    def _history_block(self) -> str:
        recent = self._history[-_HISTORY_WINDOW:]
        if not recent:
            return ""
        lines = ["Recent turns:"]
        for turn in recent:
            lines.append(f"  Player: {turn['player']}")
            summary = turn["gm"][:120].replace("\n", " ")
            lines.append(f"  GM: {summary}…")
        return "\n".join(lines) + "\n\n"


_KNOWN_VERBS: frozenset[str] = frozenset(
    ["start", "overview", "look", "enter", "go", "inspect", "talk", "clues", "case"]
)

_TOOL_CALL_RE = re.compile(r"[`{}<|]|tool_call|```", re.IGNORECASE)


def _rejoin_split_commands(commands: list[str]) -> list[str]:
    """Recombine commands the LLM split into [verb, arg] pairs, and drop garbage strings."""
    result: list[str] = []
    i = 0
    while i < len(commands):
        token = commands[i]
        # Drop any string that looks like a leaked tool-call or reasoning artifact
        if _TOOL_CALL_RE.search(token) or len(token) > 200:
            i += 1
            continue
        if token.lower() in _KNOWN_VERBS and i + 1 < len(commands):
            next_token = commands[i + 1]
            if not _TOOL_CALL_RE.search(next_token) and next_token.lower() not in _KNOWN_VERBS:
                result.append(f"{token} {next_token}")
                i += 2
                continue
        result.append(token)
        i += 1
    return result


_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Remove chain-of-thought content that reasoning models may emit.

    Handles:
    - <think>…</think> XML tags used by DeepSeek, Qwen, etc.
    - Unclosed <think> blocks (content from the tag to end of string).
    - Preamble lines that look like reasoning (e.g. "Thinking Process:", numbered
      analysis steps) before the actual prose begins.
    """
    # Remove complete <think>…</think> blocks
    text = _THINK_TAG_RE.sub("", text)
    # Remove unclosed <think> block (everything from the tag onward)
    think_start = text.lower().find("<think>")
    if think_start != -1:
        text = text[:think_start]
    text = text.strip()

    # If the text still starts with reasoning-style preamble, find where the
    # actual prose begins: the first line that starts with "You " (second-person)
    # or with a capital letter after a blank line, whichever comes first.
    if text and not text[:3].startswith("You"):
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("You ") or stripped.startswith("You'"):
                text = "\n".join(lines[i:]).strip()
                break

    return text


__all__ = ["GameMaster"]
