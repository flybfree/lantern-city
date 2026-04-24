from __future__ import annotations

import json
import shlex
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from lantern_city.bootstrap import bootstrap_city
from lantern_city.case_bootstrap import bootstrap_generated_case
from lantern_city.cases import advance_case_pressure, case_pressure_summary, note_case_progress, transition_case
from lantern_city.clues import clarify_clue
from lantern_city.engine import handle_player_request
from lantern_city.factions import (
    FactionOperation,
    faction_style_label,
    faction_tactic_label,
    run_faction_turn,
)
from lantern_city.generation.case_generation import (
    CaseGenerationRequest,
    CaseGenerationError,
    CaseGenerator,
)
from lantern_city.generation.city_seed import (
    CitySeedGenerationError,
    CitySeedGenerationRequest,
    CitySeedGenerator,
)
from lantern_city.generation.npc_response import NPCResponseGenerationResult
from lantern_city.generation.world_content import WorldContentGenerator
from lantern_city.generation.transient_response import (
    TransientGenerationError,
    generate_transient_encounter,
)
from lantern_city.transients import roll_encounter
from lantern_city.lanterns import LanternRuleProfile, apply_lantern_to_clue, is_corroborated
from lantern_city.llm_client import OpenAICompatibleConfig, OpenAICompatibleLLMClient
from lantern_city.models import (
    ActiveWorkingSet,
    CaseState,
    ClueState,
    DistrictState,
    FactionState,
    LocationState,
    NPCState,
    PlayerProgressState,
    PlayerRequest,
)
from lantern_city.progression import apply_progress_change, get_tier
from lantern_city.seed_schema import validate_city_seed
from lantern_city.simulation import WorldTurnPlan, plan_world_turn, turn_label
from lantern_city.social import (
    append_memory_entry,
    apply_relationship_shift,
    build_offscreen_memory_entry,
    run_offscreen_npc_tick,
)
from lantern_city.store import SQLiteStore
from lantern_city.log import get_logger

log = get_logger(__name__)

TURN_ZERO = "turn_0"

_AWS_ID = "aws_player_001"

_MODEL_QUALITY_PROBE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "task_type": {"type": "string"},
        "request_id": {"type": "string"},
        "summary_text": {"type": "string"},
        "structured_updates": {
            "type": "object",
            "properties": {
                "dialogue_act": {"type": "string"},
                "npc_stance": {"type": "string"},
                "relationship_shift": {
                    "type": "object",
                    "properties": {
                        "trust_delta": {"type": "number"},
                        "suspicion_delta": {"type": "number"},
                        "fear_delta": {"type": "number"},
                        "tag": {"type": ["string", "null"]},
                    },
                    "required": ["trust_delta", "suspicion_delta", "fear_delta", "tag"],
                    "additionalProperties": False,
                },
                "clue_effects": {"type": "array"},
                "access_effects": {"type": "array"},
                "redirect_targets": {"type": "array"},
            },
            "required": [
                "dialogue_act",
                "npc_stance",
                "relationship_shift",
                "clue_effects",
                "access_effects",
                "redirect_targets",
            ],
            "additionalProperties": False,
        },
        "cacheable_text": {
            "type": "object",
            "properties": {
                "npc_line": {"type": "string"},
                "follow_up_suggestions": {"type": "array", "items": {"type": "string"}},
                "exit_line_if_needed": {"type": ["string", "null"]},
            },
            "required": ["npc_line", "follow_up_suggestions", "exit_line_if_needed"],
            "additionalProperties": False,
        },
        "confidence": {"type": "number"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "task_type",
        "request_id",
        "summary_text",
        "structured_updates",
        "cacheable_text",
        "confidence",
        "warnings",
    ],
    "additionalProperties": False,
}

_MVP_BASELINE_CASE_IDS: frozenset[str] = frozenset({"case_missing_clerk"})


@dataclass(frozen=True, slots=True)
class _AppliedWorldTurn:
    updated_at: str
    catch_up_turns: int
    faction_updates: list[str]
    case_pressure_updates: list[str]
    offscreen_updates: list[str]


@dataclass(slots=True)
class LanternCityApp:
    database_path: str | Path
    llm_config: OpenAICompatibleConfig | None = None
    startup_mode: str = "auto"
    store: SQLiteStore = field(init=False)

    def __post_init__(self) -> None:
        self.store = SQLiteStore(self.database_path)

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def start_new_game(
        self,
        concept: str | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> str:
        def _emit(msg: str) -> None:
            if on_progress is not None:
                on_progress(msg)

        existing_city = self._city()
        startup_mode = self._resolved_startup_mode()
        if existing_city is not None:
            case = self._active_case(existing_city)
            case_title = "None introduced yet" if case is None else self._display_case_title(case.title)
            return (
                f"Existing game loaded: {existing_city.id}\n"
                f"Districts: {', '.join(existing_city.district_ids)}\n"
                f"Startup mode: {startup_mode}\n"
                f"Active case: {case_title}"
            )

        model_check_summary: str | None = None
        if startup_mode == "generated_runtime":
            _emit("[llm] Running model quality check…")
            model_check_summary = self._probe_llm_quality()
            _emit(f"[llm] {model_check_summary}")
            _emit("[city] Generating city seed via LLM…")
            seed = self._generate_city_seed(concept, on_progress=on_progress)
        else:
            _emit("[city] Loading default city seed (no LLM configured)…")
            seed = validate_city_seed(_load_default_seed())

        _emit("[city] Bootstrapping city structure…")
        result = bootstrap_city(seed, self.store)
        _emit(f"[city] Structure ready: {result.city_id}")

        if startup_mode == "generated_runtime":
            _emit("[city] Generating world content (locations, clues, NPC placement)…")
            self._generate_world_content(on_progress=on_progress)
            _emit("[city] Generating latent cases…")
            self._generate_latent_cases(count=2)
            _emit("[city] Latent cases ready.")
        else:
            _emit("[city] Seeding authored scene objects…")
            self._seed_authored_scene_objects()
            self._activate_authored_start_case()

        city = self._require_city()
        case = self._active_case(city)
        case_title = "None introduced yet" if case is None else self._display_case_title(case.title)
        first_district = (
            case.involved_district_ids[0]
            if case and case.involved_district_ids
            else (city.district_ids[0] if city.district_ids else "unknown")
        )
        return (
            f"Lantern City ready: seeded {result.city_id}\n"
            f"Districts: {', '.join(result.district_ids)}\n"
            f"Startup mode: {startup_mode}\n"
            f"Active case: {case_title}\n"
            f"{'' if model_check_summary is None else model_check_summary + chr(10)}"
            f"Next: enter {first_district}"
        )

    def run_command(self, command: str) -> str:
        log.debug("run_command %r", command)
        parts = shlex.split(command)
        if not parts:
            raise ValueError("Command cannot be empty")

        verb = parts[0].lower()
        if verb == "start":
            concept = " ".join(parts[1:]) if len(parts) > 1 else None
            return self.start_new_game(concept=concept)
        if verb == "overview":
            return self.overview()
        if verb == "status":
            return self.status()
        if verb == "clues":
            return self.clues()
        if verb == "journal":
            return self.journal()
        if verb in {"board", "caseboard"}:
            return self.case_board(parts[1] if len(parts) > 1 else None)
        if verb == "leads":
            return self.strongest_leads()
        if verb in {"matters", "standout"}:
            return self.what_matters_here()
        if verb == "compare" and len(parts) >= 3:
            return self.compare_clues(parts[1], parts[2])
        if verb == "go" and len(parts) >= 2:
            return self.go(parts[1])
        if verb == "look":
            return self.look(parts[1] if len(parts) >= 2 else None)
        if verb == "enter" and len(parts) >= 2:
            return self.enter_district(self._resolve_district_id(parts[1]))
        if verb == "talk" and len(parts) >= 3:
            return self.talk_to_npc(parts[1], " ".join(parts[2:]))
        if verb == "inspect" and len(parts) >= 2:
            return self.inspect_location(parts[1])
        if verb == "case" and len(parts) >= 2:
            return self.advance_case(parts[1])
        raise ValueError(f"Unsupported command: {command}")

    def enter_district(self, district_id: str) -> str:
        log.debug("enter_district %r", district_id)
        city = self._require_city()
        turn_plan = self._plan_world_turn()
        updated_at = self._planned_updated_at(turn_plan)
        outcome = handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request("district entry", target_id=district_id, updated_at=updated_at),
            llm_config=self.llm_config,
        )
        district = outcome.active_slice.district
        if district is None:
            raise LookupError(f"District not found: {district_id}")
        existing_pos = self._load_position()
        visited = list(existing_pos.visited_district_ids) if existing_pos else []
        if district_id not in visited:
            visited.append(district_id)
        self._save_position(
            district_id=district_id,
            location_id=None,
            npc_ids=[],
            visited_district_ids=visited,
            updated_at=updated_at,
        )
        visible_npc = "None"
        preferred_npc = next(
            (npc for npc in outcome.active_slice.npcs if npc.id == "npc_shrine_keeper"),
            None,
        )
        if preferred_npc is not None:
            visible_npc = preferred_npc.name
        elif outcome.active_slice.npcs:
            visible_npc = outcome.active_slice.npcs[0].name
        available_npcs = (
            ", ".join(f"{npc.id} ({npc.name})" for npc in outcome.active_slice.npcs)
            if outcome.active_slice.npcs
            else "None"
        )
        available_locations = (
            ", ".join(outcome.active_slice.district.visible_locations)
            if outcome.active_slice.district is not None and outcome.active_slice.district.visible_locations
            else "None"
        )
        lines = [
            f"District: {district.name}",
            f"Lanterns: {district.lantern_condition}",
            f"Notable NPC: {visible_npc}",
            f"Available NPC IDs: {available_npcs}",
            f"Available location IDs: {available_locations}",
            f"Summary: {outcome.response.narrative_text}",
        ]
        self._append_scene_affordances(
            lines,
            learned=outcome.response.learned,
            visible_npcs=outcome.response.visible_npcs,
            notable_objects=outcome.response.notable_objects,
            exits=outcome.response.exits,
            case_relevance=outcome.response.case_relevance,
            now_available=outcome.response.now_available,
            next_actions=outcome.response.next_actions,
        )
        transient_text = self._maybe_transient_encounter(district_id, district, updated_at=updated_at)
        if transient_text:
            lines.append(f"\n{transient_text}")
        turn_notices = self._apply_world_turn_plan(
            turn_plan,
            focus_district_id=district_id,
        )
        if turn_notices.catch_up_turns:
            lines.append(f"[Time passes: {turn_notices.catch_up_turns} extra turn(s)]")
        if turn_notices.faction_updates:
            lines.append("\nFaction pressure:")
            lines.extend(f"  - {line}" for line in _prioritized_faction_updates(turn_notices.faction_updates))
        if turn_notices.case_pressure_updates:
            lines.append("\nCase pressure:")
            lines.extend(f"  - {line}" for line in turn_notices.case_pressure_updates[:4])
        if turn_notices.offscreen_updates:
            lines.append("\nOffscreen movement:")
            lines.extend(f"  - {line}" for line in turn_notices.offscreen_updates[:4])
        return "\n".join(lines)

    def talk_to_npc(self, npc_id: str, prompt: str) -> str:
        city = self._require_city()
        progress = self._require_progress()
        turn_plan = self._plan_world_turn()
        updated_at = self._planned_updated_at(turn_plan)

        # Peek at any pending case hook BEFORE generation so the LLM can weave it in
        pending_case, case_intro_text = self._peek_npc_case_hook(npc_id)

        outcome = handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request(
                "talk to NPC",
                target_id=npc_id,
                input_text=prompt,
                updated_at=updated_at,
            ),
            llm_config=self.llm_config,
            progress=progress,
            case_intro_text=case_intro_text,
        )
        npc = outcome.active_slice.npcs[0]
        self._save_position(npc_ids=[npc.id], updated_at=updated_at)
        clue = self._npc_clue(npc)
        progress = self._require_progress()
        updates = []

        if clue is not None and clue.reliability != "solid":
            clue = clarify_clue(
                clue,
                clarification_text=f"{npc.name} provides testimony connecting the evidence to the case.",
                updated_at=updated_at,
            )
            updates.append(clue)

        progress, _ = apply_progress_change(
            progress,
            track="clue_mastery",
            amount=4,
            reason=f"Gained testimony from {npc.name}.",
            updated_at=updated_at,
        )
        updates.append(progress)
        self.store.save_objects_atomically(updates)
        if clue is not None:
            self._acquire_clues([clue.id], updated_at=updated_at)

        district = outcome.active_slice.district
        propagation_notices = []
        if district is not None:
            city = self._require_city()
            propagation_notices = self._propagate_missingness(city, district, updated_at=updated_at)

        # Activate the pending case now that dialogue has surfaced it
        progressed_case_ids: set[str] = set()
        if pending_case is not None:
            activated = transition_case(pending_case, "active", updated_at=updated_at)
            self.store.save_object(activated)
            self._introduce_case(pending_case.id, updated_at=updated_at)
            progressed_case_ids.add(pending_case.id)
        if clue is not None and clue.related_case_ids:
            progressed_case_ids.update(clue.related_case_ids)

        lines = [outcome.response.narrative_text]
        if clue is not None:
            lines.append(f'[Clue: {_clue_label(clue.id)} — {clue.reliability}]')
        if _has_pre_case_signal(outcome.response.case_relevance):
            lines.append("[New lead]")
        if pending_case is not None:
            lines.append(f'[Case opened: {pending_case.title}]')
        lines.extend(propagation_notices)
        self._append_scene_affordances(
            lines,
            learned=outcome.response.learned,
            visible_npcs=outcome.response.visible_npcs,
            notable_objects=outcome.response.notable_objects,
            exits=outcome.response.exits,
            case_relevance=outcome.response.case_relevance,
            now_available=outcome.response.now_available,
            next_actions=outcome.response.next_actions,
        )
        turn_notices = self._apply_world_turn_plan(
            turn_plan,
            progressed_case_ids=progressed_case_ids,
            focus_district_id=outcome.active_slice.district.id if outcome.active_slice.district else None,
            exclude_npc_ids={npc_id},
        )
        if turn_notices.catch_up_turns:
            lines.append(f"[Time passes: {turn_notices.catch_up_turns} extra turn(s)]")
        if turn_notices.faction_updates:
            lines.append("[Faction pressure]")
            lines.extend(_prioritized_faction_updates(turn_notices.faction_updates))
        if turn_notices.case_pressure_updates:
            lines.append("[Case pressure]")
            lines.extend(turn_notices.case_pressure_updates[:4])
        if turn_notices.offscreen_updates:
            lines.append("[Offscreen shifts]")
            lines.extend(turn_notices.offscreen_updates[:4])
        return "\n".join(lines)

    def inspect_location(self, location_id: str, object_name: str | None = None) -> str:
        city = self._require_city()
        progress = self._require_progress()
        turn_plan = self._plan_world_turn()
        updated_at = self._planned_updated_at(turn_plan)
        outcome = handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request(
                "inspect location",
                target_id=location_id,
                input_text=object_name or "",
                updated_at=updated_at,
            ),
            llm_config=self.llm_config,
            progress=progress,
        )
        district = outcome.active_slice.district
        if district is None:
            return outcome.response.narrative_text
        self._save_position(location_id=location_id, updated_at=updated_at)

        lantern_profile = LanternRuleProfile(
            state=district.lantern_condition,
            missingness=_missingness_level(city.missingness_pressure),
        )
        all_clues = outcome.active_slice.clues

        discoverable = [
            clue for clue in all_clues
            if not clue.related_npc_ids
        ]

        inspected_location_id = location_id
        updated_clues = [
            _apply_physical_discovery(
                apply_lantern_to_clue(
                    clue,
                    lantern_profile,
                    updated_at=updated_at,
                    corroborated=is_corroborated(clue, all_clues),
                ),
                location_id=inspected_location_id,
                updated_at=updated_at,
            )
            for clue in discoverable
        ]
        progress = self._require_progress()
        progress, _ = apply_progress_change(
            progress,
            track="lantern_understanding",
            amount=3,
            reason="Checked clues against local lantern conditions.",
            updated_at=updated_at,
        )
        self.store.save_objects_atomically([*updated_clues, progress])
        self._acquire_clues([c.id for c in updated_clues], updated_at=updated_at)

        propagation_notices = self._propagate_missingness(city, district, updated_at=updated_at)

        lines = []
        if object_name:
            lines.append(f"Examining: {object_name}")
        lines.append(outcome.response.narrative_text)
        location = outcome.active_slice.location
        if not object_name and location is not None and location.scene_objects:
            lines.append("Objects here:")
            for obj in location.scene_objects:
                lines.append(f"  - {obj}")
        if updated_clues:
            clue_status = " | ".join(
                f"{_clue_label(c.id)}: {c.reliability}" for c in updated_clues
            )
            lines.append(f"[Clue found: {clue_status}]")
        if _has_pre_case_signal(outcome.response.case_relevance):
            lines.append("[New lead]")
        lines.append(f"[Lantern: {district.lantern_condition}]")
        lines.extend(propagation_notices)
        self._append_scene_affordances(
            lines,
            learned=outcome.response.learned,
            visible_npcs=outcome.response.visible_npcs,
            notable_objects=outcome.response.notable_objects,
            exits=outcome.response.exits,
            case_relevance=outcome.response.case_relevance,
            now_available=outcome.response.now_available,
            next_actions=outcome.response.next_actions,
        )
        progressed_case_ids = {
            case_id
            for clue in updated_clues
            for case_id in clue.related_case_ids
        }
        turn_notices = self._apply_world_turn_plan(
            turn_plan,
            progressed_case_ids=progressed_case_ids,
            focus_district_id=district.id,
        )
        if turn_notices.catch_up_turns:
            lines.append(f"[Time passes: {turn_notices.catch_up_turns} extra turn(s)]")
        if turn_notices.faction_updates:
            lines.append("[Faction pressure]")
            lines.extend(_prioritized_faction_updates(turn_notices.faction_updates))
        if turn_notices.case_pressure_updates:
            lines.append("[Case pressure]")
            lines.extend(turn_notices.case_pressure_updates[:4])
        if turn_notices.offscreen_updates:
            lines.append("[Offscreen shifts]")
            lines.extend(turn_notices.offscreen_updates[:4])
        return "\n".join(lines)

    def advance_case(self, case_id: str) -> str:
        city = self._require_city()
        turn_plan = self._plan_world_turn()
        updated_at = self._planned_updated_at(turn_plan)
        handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request("review case", target_id=case_id, updated_at=updated_at),
            llm_config=self.llm_config,
        )
        case_obj = self.store.load_object("CaseState", case_id)
        if not isinstance(case_obj, CaseState):
            raise LookupError(f"Case not found: {case_id}")
        case = case_obj
        progress = self._require_progress()

        runtime_mode = _case_runtime_mode(case)

        if runtime_mode == "mvp_baseline":
            path, new_status, resolution_summary, fallout_summary = _assess_resolution(
                self.store, progress
            )
            gains = _RESOLUTION_GAINS[path]
        else:
            new_status, resolution_summary, fallout_summary = _assess_generated_resolution(
                case, self.store
            )
            path = new_status.replace(" ", "_")
            gains = _gains_for_outcome(new_status)

        updated_case = transition_case(
            case,
            new_status,
            updated_at=updated_at,
            resolution_summary=resolution_summary,
            fallout_summary=fallout_summary,
        )
        self.store.save_object(updated_case)

        progress = self._require_progress()
        for track, amount, reason in gains:
            progress, _ = apply_progress_change(
                progress,
                track=track,
                amount=amount,
                reason=reason,
                updated_at=updated_at,
            )
        self.store.save_object(progress)

        # Generate a new latent case if the pipeline is running low
        if self._resolved_startup_mode() == "generated_runtime":
            city = self._require_city()
            non_terminal = [
                obj
                for cid in city.active_case_ids
                if isinstance(obj := self.store.load_object("CaseState", cid), CaseState)
                and obj.status not in {"solved", "partially solved", "failed"}
            ]
            if len(non_terminal) < 2:
                self._generate_latent_cases(count=1)

        lines = [
            f"Case status: {updated_case.status}",
            f"Resolution: {path.replace('_', ' ')}",
            f"Case: {updated_case.title}",
            f"Lantern understanding: {progress.lantern_understanding.score} ({progress.lantern_understanding.tier})",
            f"Access: {progress.access.score} ({progress.access.tier})",
            f"Leverage: {progress.leverage.score} ({progress.leverage.tier})",
        ]
        city = self._require_city()
        latent_remaining = [
            obj
            for cid in city.active_case_ids
            if isinstance(obj := self.store.load_object("CaseState", cid), CaseState)
            and obj.status == "latent"
        ]
        if latent_remaining:
            lines.append("")
            lines.append("No new case has been introduced yet.")
            lines.append("Find the next lead through district context or NPC interaction.")
        lines.append("")
        lines.append("Follow-up:")
        lines.append("  - overview")
        lines.append("  - leads")
        turn_notices = self._apply_world_turn_plan(
            turn_plan,
            progressed_case_ids={case_id},
        )
        if turn_notices.catch_up_turns:
            lines.append(f"\n[Time passes: {turn_notices.catch_up_turns} extra turn(s)]")
        if turn_notices.faction_updates:
            lines.append("\nFaction pressure:")
            lines.extend(f"  - {line}" for line in _prioritized_faction_updates(turn_notices.faction_updates))
        if turn_notices.case_pressure_updates:
            lines.append("\nCase pressure:")
            lines.extend(f"  - {line}" for line in turn_notices.case_pressure_updates[:4])
        if turn_notices.offscreen_updates:
            lines.append("\nOffscreen shifts:")
            lines.extend(f"  - {line}" for line in turn_notices.offscreen_updates[:4])
        return "\n".join(lines)

    def _run_case_pressure_updates(
        self,
        *,
        updated_at: str,
        progressed_case_ids: set[str],
        focus_district_id: str | None = None,
    ) -> list[str]:
        city = self._require_city()
        cases = [
            case for case_id in city.active_case_ids
            if isinstance(case := self.store.load_object("CaseState", case_id), CaseState)
        ]

        updated_cases: list[CaseState] = []
        extra_updates: list[RuntimeModel] = []
        notices: list[str] = []
        for case in cases:
            if case.status == "latent":
                continue
            if focus_district_id is not None and focus_district_id not in case.involved_district_ids:
                continue

            current = case
            if case.id in progressed_case_ids:
                current = note_case_progress(
                    current,
                    updated_at=updated_at,
                    reason="player advanced the investigation",
                )
                notices.append(f"{case.title}: {case_pressure_summary(current)}")
            else:
                current, pressure_notices = advance_case_pressure(current, updated_at=updated_at)
                notices.extend(pressure_notices)
                current, style_updates, style_notices = self._apply_case_faction_style_drift(
                    current,
                    updated_at=updated_at,
                )
                extra_updates.extend(style_updates)
                notices.extend(style_notices)
                notices.append(f"{case.title}: {case_pressure_summary(current)}")

            if current != case:
                updated_cases.append(current.model_copy(update={"version": case.version + 1}))

        if updated_cases or extra_updates:
            self.store.save_objects_atomically([*updated_cases, *extra_updates])
        return notices

    def _apply_case_faction_style_drift(
        self,
        case: CaseState,
        *,
        updated_at: str,
    ) -> tuple[CaseState, list[RuntimeModel], list[str]]:
        if _case_runtime_mode(case) != "evolved_runtime":
            return case, [], []

        current = case
        updates: list[RuntimeModel] = []
        notices: list[str] = []
        for faction_id in current.involved_faction_ids:
            faction = self.store.load_object("FactionState", faction_id)
            if not isinstance(faction, FactionState):
                continue
            style = faction_style_label(faction)
            if style == "records control":
                current, clue_updates, clue_notices = self._apply_records_case_drift(
                    current,
                    faction=faction,
                    updated_at=updated_at,
                )
                updates.extend(clue_updates)
                notices.extend(clue_notices)
            elif style == "civic enforcement":
                district_updates, district_notices = self._apply_civic_case_drift(
                    current,
                    faction=faction,
                    updated_at=updated_at,
                )
                updates.extend(district_updates)
                notices.extend(district_notices)
        return current, updates, notices

    def _apply_records_case_drift(
        self,
        case: CaseState,
        *,
        faction: FactionState,
        updated_at: str,
    ) -> tuple[CaseState, list[RuntimeModel], list[str]]:
        if case.pressure_level not in {"rising", "urgent"}:
            return case, [], []
        known_ids = list(case.known_clue_ids)
        if not known_ids:
            known_ids = [
                clue.id
                for clue in self.store.list_objects("ClueState")
                if isinstance(clue, ClueState) and case.id in clue.related_case_ids
            ]
        for clue_id in known_ids:
            clue = self.store.load_object("ClueState", clue_id)
            if not isinstance(clue, ClueState):
                continue
            if clue.source_type != "document" or clue.reliability not in {"credible", "uncertain"}:
                continue
            next_reliability = "uncertain" if clue.reliability == "credible" else "unstable"
            updated_clue = clue.model_copy(update={"reliability": next_reliability, "updated_at": updated_at})
            risk_flag = f"records_drift:{faction.id}"
            if risk_flag not in case.offscreen_risk_flags:
                case = case.model_copy(
                    update={
                        "offscreen_risk_flags": [*case.offscreen_risk_flags, risk_flag],
                        "updated_at": updated_at,
                    }
                )
            return (
                case,
                [updated_clue.model_copy(update={"version": clue.version + 1})],
                [
                    f"{faction.name} is muddying the paper trail around {case.title}.",
                    f"[Pressure: {_clue_label(clue.id)} is slipping - reliability now {next_reliability}]",
                ],
            )
        return case, [], []

    def _apply_civic_case_drift(
        self,
        case: CaseState,
        *,
        faction: FactionState,
        updated_at: str,
    ) -> tuple[list[RuntimeModel], list[str]]:
        if case.pressure_level not in {"rising", "urgent"}:
            return [], []
        updates: list[RuntimeModel] = []
        notices: list[str] = []
        for district_id in case.involved_district_ids:
            district = self.store.load_object("DistrictState", district_id)
            if not isinstance(district, DistrictState):
                continue
            next_access = _surveil_district_access(district.current_access_level)
            surveillance_flag = f"civic_pressure:{faction.id}"
            active_problems = list(district.active_problems)
            changed = False
            if surveillance_flag not in active_problems:
                active_problems = [*active_problems, surveillance_flag][-6:]
                changed = True
            if next_access != district.current_access_level:
                changed = True
            if not changed:
                continue
            updates.append(
                district.model_copy(
                    update={
                        "active_problems": active_problems,
                        "current_access_level": next_access,
                        "updated_at": updated_at,
                        "version": district.version + 1,
                    }
                )
            )
            notices.append(f"{faction.name} is narrowing official access in {district.name}.")
            break
        for npc_id in case.npc_pressure_targets[:1]:
            npc = self.store.load_object("NPCState", npc_id)
            if not isinstance(npc, NPCState):
                continue
            pressured = apply_relationship_shift(
                npc,
                trust_delta=-0.02,
                suspicion_delta=0.05,
                tag=f"civic_pressure_{faction.id}",
                updated_at=updated_at,
            ).npc
            if pressured == npc:
                continue
            pressured = append_memory_entry(
                pressured.model_copy(
                    update={
                        "offscreen_state": "obstructing",
                        "updated_at": updated_at,
                    }
                ),
                memory_entry=build_offscreen_memory_entry(
                    updated_at=updated_at,
                    offscreen_state="obstructing",
                    summary_text=f"procedural pressure from {faction.name} over {case.title}",
                    location_id=npc.location_id,
                ),
                updated_at=updated_at,
            )
            updates.append(pressured.model_copy(update={"version": npc.version + 1}))
            notices.append(f"{faction.name} is making {npc.name} more procedural and guarded.")
            break
        return updates, notices

    def _run_faction_updates(
        self,
        *,
        city: CityState,
        updated_at: str,
        focus_district_id: str | None = None,
        exclude_npc_ids: set[str] | None = None,
    ) -> list[str]:
        factions = [
            faction
            for faction_id in city.faction_ids
            if isinstance(faction := self.store.load_object("FactionState", faction_id), FactionState)
        ]
        related_cases = [
            case
            for case_id in city.active_case_ids
            if isinstance(case := self.store.load_object("CaseState", case_id), CaseState)
            and case.status != "latent"
            and (focus_district_id is None or focus_district_id in case.involved_district_ids)
        ]
        focus_district = (
            self.store.load_object("DistrictState", focus_district_id)
            if focus_district_id is not None
            else None
        )
        updated_factions: list[FactionState] = []
        notices: list[str] = []
        for faction in factions:
            result = run_faction_turn(
                faction,
                city=city,
                related_cases=[case for case in related_cases if faction.id in case.involved_faction_ids],
                updated_at=updated_at,
                focus_district_id=focus_district_id,
                district_access_level=(
                    focus_district.current_access_level
                    if isinstance(focus_district, DistrictState)
                    else None
                ),
            )
            if result.faction != faction:
                updated_factions.append(result.faction.model_copy(update={"version": faction.version + 1}))
            notices.extend(
                self._apply_faction_operations(
                    faction=result.faction,
                    operations=result.operations,
                    updated_at=updated_at,
                    exclude_npc_ids=exclude_npc_ids or set(),
                )
            )
            notices.extend(result.notices)
        if updated_factions:
            self.store.save_objects_atomically(updated_factions)
        return notices

    def _apply_faction_operations(
        self,
        *,
        faction: FactionState,
        operations: list[FactionOperation],
        updated_at: str,
        exclude_npc_ids: set[str],
    ) -> list[str]:
        notices: list[str] = []
        for operation in operations:
            if operation.kind == "district_pressure" and operation.district_id:
                notices.extend(
                    self._apply_faction_district_pressure(
                        faction=faction,
                        district_id=operation.district_id,
                        updated_at=updated_at,
                    )
                )
            elif operation.kind == "district_surveillance" and operation.district_id:
                notices.extend(
                    self._apply_faction_district_surveillance(
                        faction=faction,
                        district_id=operation.district_id,
                        updated_at=updated_at,
                    )
                )
            elif operation.kind == "case_interference" and operation.case_id:
                notices.extend(
                    self._apply_faction_case_interference(
                        faction=faction,
                        case_id=operation.case_id,
                        updated_at=updated_at,
                    )
                )
            elif operation.kind == "case_coverup" and operation.case_id:
                notices.extend(
                    self._apply_faction_case_coverup(
                        faction=faction,
                        case_id=operation.case_id,
                        updated_at=updated_at,
                    )
                )
            elif operation.kind == "case_isolation" and operation.case_id:
                notices.extend(
                    self._apply_faction_case_isolation(
                        faction=faction,
                        case_id=operation.case_id,
                        updated_at=updated_at,
                    )
                )
            elif (
                operation.kind == "npc_pressure"
                and operation.case_id
                and operation.npc_id
                and operation.npc_id not in exclude_npc_ids
            ):
                notices.extend(
                    self._apply_faction_npc_pressure(
                        faction=faction,
                        case_id=operation.case_id,
                        npc_id=operation.npc_id,
                        updated_at=updated_at,
                    )
                )
        return notices

    def _apply_faction_district_pressure(
        self,
        *,
        faction: FactionState,
        district_id: str,
        updated_at: str,
    ) -> list[str]:
        district = self.store.load_object("DistrictState", district_id)
        if not isinstance(district, DistrictState):
            return []
        pressure_flag = f"faction_pressure:{faction.id}"
        active_problems = list(district.active_problems)
        changed = False
        if pressure_flag not in active_problems:
            active_problems = [*active_problems, pressure_flag][-6:]
            changed = True
        next_access = _tighten_district_access(district.current_access_level)
        if next_access != district.current_access_level:
            changed = True
        if not changed:
            return []
        updated = district.model_copy(
            update={
                "active_problems": active_problems,
                "current_access_level": next_access,
                "updated_at": updated_at,
                "version": district.version + 1,
            }
        )
        self.store.save_object(updated)
        notices = [f"{faction.name} is constricting access in {district.name}."]
        if pressure_flag in active_problems:
            notices.append(f"{district.name} is now carrying active faction pressure from {faction.name}.")
        return notices

    def _apply_faction_district_surveillance(
        self,
        *,
        faction: FactionState,
        district_id: str,
        updated_at: str,
    ) -> list[str]:
        district = self.store.load_object("DistrictState", district_id)
        if not isinstance(district, DistrictState):
            return []
        surveillance_flag = f"faction_surveillance:{faction.id}"
        active_problems = list(district.active_problems)
        changed = False
        if surveillance_flag not in active_problems:
            active_problems = [*active_problems, surveillance_flag][-6:]
            changed = True
        next_access = _surveil_district_access(district.current_access_level)
        if next_access != district.current_access_level:
            changed = True
        if not changed:
            return []
        updated = district.model_copy(
            update={
                "active_problems": active_problems,
                "current_access_level": next_access,
                "updated_at": updated_at,
                "version": district.version + 1,
            }
        )
        self.store.save_object(updated)
        return [f"{faction.name} is watching movement through {district.name}."]

    def _apply_faction_case_interference(
        self,
        *,
        faction: FactionState,
        case_id: str,
        updated_at: str,
    ) -> list[str]:
        case = self.store.load_object("CaseState", case_id)
        if not isinstance(case, CaseState) or _case_runtime_mode(case) != "evolved_runtime":
            return []
        risk_flag = f"faction_pressure:{faction.id}"
        district_effect = f"interference:{faction.id}"
        risk_flags = list(case.offscreen_risk_flags)
        district_effects = list(case.district_effects)
        idle_turns = case.time_since_last_progress + (1 if case.time_since_last_progress > 0 else 0)
        changed = False
        if risk_flag not in risk_flags:
            risk_flags = [*risk_flags, risk_flag]
            changed = True
        if district_effect not in district_effects:
            district_effects = [*district_effects, district_effect][-6:]
            changed = True
        if idle_turns != case.time_since_last_progress:
            changed = True
        next_window = "narrowing" if case.active_resolution_window == "open" else case.active_resolution_window
        if next_window != case.active_resolution_window:
            changed = True
        if not changed:
            return []
        updated = case.model_copy(
            update={
                "offscreen_risk_flags": risk_flags,
                "district_effects": district_effects,
                "time_since_last_progress": idle_turns,
                "active_resolution_window": next_window,
                "updated_at": updated_at,
                "version": case.version + 1,
            }
        )
        self.store.save_object(updated)
        return [f"{faction.name} is tightening pressure around {case.title}."]

    def _apply_faction_case_coverup(
        self,
        *,
        faction: FactionState,
        case_id: str,
        updated_at: str,
    ) -> list[str]:
        case = self.store.load_object("CaseState", case_id)
        if not isinstance(case, CaseState) or _case_runtime_mode(case) != "evolved_runtime":
            return []
        risk_flag = f"coverup:{faction.id}"
        district_effect = f"coverup:{faction.id}"
        if risk_flag in case.offscreen_risk_flags and district_effect in case.district_effects:
            return []
        updated = case.model_copy(
            update={
                "offscreen_risk_flags": [*case.offscreen_risk_flags, risk_flag]
                if risk_flag not in case.offscreen_risk_flags
                else case.offscreen_risk_flags,
                "district_effects": [*case.district_effects, district_effect][-6:]
                if district_effect not in case.district_effects
                else case.district_effects,
                "updated_at": updated_at,
                "version": case.version + 1,
            }
        )
        self.store.save_object(updated)
        return [f"{faction.name} is covering its tracks around {case.title}."]

    def _apply_faction_case_isolation(
        self,
        *,
        faction: FactionState,
        case_id: str,
        updated_at: str,
    ) -> list[str]:
        case = self.store.load_object("CaseState", case_id)
        if not isinstance(case, CaseState) or _case_runtime_mode(case) != "evolved_runtime":
            return []
        risk_flag = f"isolation:{faction.id}"
        district_effect = f"isolation:{faction.id}"
        next_window = "narrowing"
        updated = case.model_copy(
            update={
                "offscreen_risk_flags": [*case.offscreen_risk_flags, risk_flag]
                if risk_flag not in case.offscreen_risk_flags
                else case.offscreen_risk_flags,
                "district_effects": [*case.district_effects, district_effect][-6:]
                if district_effect not in case.district_effects
                else case.district_effects,
                "active_resolution_window": next_window,
                "updated_at": updated_at,
                "version": case.version + 1,
            }
        )
        if updated == case:
            return []
        self.store.save_object(updated)
        return [f"{faction.name} is isolating witnesses around {case.title}."]

    def _apply_faction_npc_pressure(
        self,
        *,
        faction: FactionState,
        case_id: str,
        npc_id: str,
        updated_at: str,
    ) -> list[str]:
        case = self.store.load_object("CaseState", case_id)
        npc = self.store.load_object("NPCState", npc_id)
        if (
            not isinstance(case, CaseState)
            or not isinstance(npc, NPCState)
            or _case_runtime_mode(case) != "evolved_runtime"
        ):
            return []
        pressure_event = f"pressured by {faction.name} over {case.title}"
        updated = apply_relationship_shift(
            npc,
            trust_delta=-0.03,
            suspicion_delta=0.08,
            tag=f"faction_pressure_{faction.id}",
            updated_at=updated_at,
        ).npc
        recent_events = [*updated.recent_events, pressure_event][-6:]
        updated = append_memory_entry(
            updated.model_copy(
                update={
                    "offscreen_state": "obstructing",
                    "recent_events": recent_events,
                    "updated_at": updated_at,
                }
            ),
            memory_entry=build_offscreen_memory_entry(
                updated_at=updated_at,
                offscreen_state="obstructing",
                summary_text=pressure_event,
                location_id=npc.location_id,
            ),
            updated_at=updated_at,
        )
        if updated == npc:
            return []
        self.store.save_object(updated.model_copy(update={"version": npc.version + 1}))
        return [f"{faction.name} is leaning on {npc.name} over {case.title}."]

    def _run_offscreen_npc_updates(
        self,
        *,
        updated_at: str,
        focus_district_id: str | None = None,
        exclude_npc_ids: set[str] | None = None,
    ) -> list[str]:
        exclude = exclude_npc_ids or set()
        districts = {
            district.id: district
            for district in self.store.list_objects("DistrictState")
            if isinstance(district, DistrictState)
        }
        npcs = [
            npc for npc in self.store.list_objects("NPCState")
            if isinstance(npc, NPCState) and npc.id not in exclude
        ]

        updated_npcs: list[NPCState] = []
        changes: list[str] = []
        for npc in npcs:
            if npc.updated_at == updated_at:
                continue
            if focus_district_id is not None and npc.district_id != focus_district_id:
                continue
            if npc.role_category == "informant" and npc.relevance_rating < 0.4:
                continue
            district = districts.get(npc.district_id or "")
            visible_location_ids = [] if district is None else district.visible_locations
            result = run_offscreen_npc_tick(
                npc,
                visible_location_ids=visible_location_ids,
                updated_at=updated_at,
            )
            if (
                result.npc.offscreen_state != npc.offscreen_state
                or result.npc.location_id != npc.location_id
                or result.npc.recent_events != npc.recent_events
                or result.npc.memory_log != npc.memory_log
            ):
                updated_npcs.append(result.npc.model_copy(update={"version": npc.version + 1}))
                changes.extend(result.state_changes)

        if updated_npcs:
            self.store.save_objects_atomically(updated_npcs)
        return changes

    def _plan_world_turn(self) -> WorldTurnPlan:
        city = self._require_city()
        pos = self._load_position()
        last_meaningful_action_at = None if pos is None else pos.last_meaningful_action_at
        if self._resolved_startup_mode() == "mvp_baseline":
            last_meaningful_action_at = None
        return plan_world_turn(
            current_time_index=city.time_index,
            last_meaningful_action_at=last_meaningful_action_at,
            now=self._now(),
        )

    def _planned_updated_at(self, turn_plan: WorldTurnPlan) -> str:
        city = self._require_city()
        return turn_label(city.time_index + turn_plan.total_turns)

    def _apply_world_turn_plan(
        self,
        turn_plan: WorldTurnPlan,
        *,
        progressed_case_ids: set[str] | None = None,
        focus_district_id: str | None = None,
        exclude_npc_ids: set[str] | None = None,
    ) -> _AppliedWorldTurn:
        city = self._require_city()
        current_city = city
        faction_updates: list[str] = []
        case_pressure_updates: list[str] = []
        offscreen_updates: list[str] = []
        progressed_ids = progressed_case_ids or set()

        for step_index in range(turn_plan.total_turns):
            next_time_index = current_city.time_index + 1
            updated_at = turn_label(next_time_index)
            updated_city = current_city.model_copy(
                update={
                    "time_index": next_time_index,
                    "updated_at": updated_at,
                    "version": current_city.version + 1,
                }
            )
            self.store.save_object(updated_city)
            current_city = updated_city

            faction_updates.extend(
                self._run_faction_updates(
                    city=current_city,
                    updated_at=updated_at,
                    focus_district_id=focus_district_id,
                    exclude_npc_ids=exclude_npc_ids,
                )
            )

            step_progress = progressed_ids if step_index == turn_plan.total_turns - 1 else set()
            case_pressure_updates.extend(
                self._run_case_pressure_updates(
                    updated_at=updated_at,
                    progressed_case_ids=step_progress,
                    focus_district_id=focus_district_id,
                )
            )
            offscreen_updates.extend(
                self._run_offscreen_npc_updates(
                    updated_at=updated_at,
                    focus_district_id=focus_district_id,
                    exclude_npc_ids=exclude_npc_ids,
                )
            )

        self._mark_meaningful_action(
            current_time_iso=turn_plan.current_time_iso,
            updated_at=current_city.updated_at,
        )
        return _AppliedWorldTurn(
            updated_at=current_city.updated_at,
            catch_up_turns=turn_plan.catch_up_turns,
            faction_updates=faction_updates,
            case_pressure_updates=case_pressure_updates,
            offscreen_updates=offscreen_updates,
        )

    def _mark_meaningful_action(self, *, current_time_iso: str, updated_at: str) -> None:
        self._save_position(
            last_meaningful_action_at=current_time_iso,
            updated_at=updated_at,
        )

    def _append_scene_affordances(
        self,
        lines: list[str],
        *,
        learned: list[str] | None = None,
        visible_npcs: list[str] | None = None,
        notable_objects: list[str] | None = None,
        exits: list[str] | None = None,
        case_relevance: list[str] | None = None,
        now_available: list[str] | None = None,
        next_actions: list[str] | None = None,
    ) -> None:
        if learned:
            lines.append("What you learned:")
            for item in learned[:4]:
                lines.append(f"  - {item}")
        if visible_npcs:
            lines.append("Who matters here:")
            for item in visible_npcs[:4]:
                lines.append(f"  - {item}")
        if notable_objects:
            lines.append("What stands out:")
            for item in notable_objects[:4]:
                lines.append(f"  - {item}")
        if exits:
            lines.append("Exits and routes:")
            for item in exits[:4]:
                lines.append(f"  - {item}")
        if case_relevance:
            lines.append("Case relevance:")
            for item in case_relevance[:4]:
                lines.append(f"  - {item}")
        if now_available:
            lines.append("Now available:")
            for item in now_available[:4]:
                lines.append(f"  - {item}")
        if next_actions:
            lines.append("Next actions:")
            for item in next_actions[:4]:
                lines.append(f"  - {item}")

    def overview(self) -> str:
        city = self._require_city()
        pos = self._load_position()
        lines = ["=== Lantern City ==="]
        if pos and pos.district_id:
            district = self._district(pos.district_id)
            loc_label = ""
            if pos.location_id:
                loc = self.store.load_object("LocationState", pos.location_id)
                if isinstance(loc, LocationState):
                    loc_label = f" / {loc.name}"
            d_name = district.name if district else pos.district_id
            lines.append(f"You are in: {d_name}{loc_label}")
            lines.append("")
        # Build a map of district_id → case titles that involve it (only non-latent cases)
        cases = [
            obj
            for cid in city.active_case_ids
            if isinstance(obj := self.store.load_object("CaseState", cid), CaseState)
            and obj.status != "latent"
        ]
        district_cases: dict[str, list[str]] = {}
        for case in cases:
            for did in case.involved_district_ids:
                district_cases.setdefault(did, []).append(case.title)

        for did in city.district_ids:
            district = self._district(did)
            if district is None:
                continue
            loc_count = len(district.visible_locations)
            npc_count = len(district.relevant_npc_ids)
            case_tag = ""
            if did in district_cases:
                case_tag = f"  [CASE: {', '.join(district_cases[did])}]"
            lines.append(
                f"  {district.name} [{district.lantern_condition}]"
                f"  — {loc_count} location(s), {npc_count} known NPC(s)  ({did}){case_tag}"
            )
        faction_reads = self._faction_pressure_reads(current_district_id=pos.district_id if pos else None, limit=4)
        if faction_reads:
            lines.append("")
            lines.append("Faction posture:")
            for read in faction_reads:
                lines.append(f"  - {read}")
        lines.append("")
        lines.append("Active cases:")
        if cases:
            for case in cases:
                involved = ", ".join(case.involved_district_ids) or "—"
                lines.append(f"  [{case.status}] {case.title}  ({case.id})")
                lines.append(f"    Involved districts: {involved}")
        else:
            lines.append("  None")
        return "\n".join(lines)

    def status(self) -> str:
        city = self._require_city()
        pos = self._load_position()
        progress = self._require_progress()
        clue_objects = self._load_clues([] if pos is None else pos.clue_ids)
        credible_count = sum(1 for clue in clue_objects if clue.reliability in _CREDIBLE_RELIABILITIES)
        uncertain_count = sum(
            1
            for clue in clue_objects
            if clue.reliability not in _CREDIBLE_RELIABILITIES and clue.reliability != "contradicted"
        )
        contradicted_count = sum(1 for clue in clue_objects if clue.reliability == "contradicted")
        cases = self._known_nonlatent_cases(city, pos)

        lines = ["=== Investigator Status ==="]
        if pos is not None and pos.district_id:
            district = self._district(pos.district_id)
            lines.append(f"District: {district.name if district is not None else pos.district_id}")
            if pos.location_id:
                location = self.store.load_object("LocationState", pos.location_id)
                if isinstance(location, LocationState):
                    lines.append(f"Location: {location.name}")
        else:
            lines.append("District: None")
        if cases:
            lines.append(f"Current case: {cases[0].title} [{cases[0].status}]")
            lines.append(f"Case pressure: {cases[0].pressure_level}")
            institutional_pressure = self._case_institutional_pressure_read(cases[0])
            if institutional_pressure:
                lines.append(f"Institutional pressure: {institutional_pressure}")
        else:
            lines.append("Current case: None")
        faction_reads = self._faction_pressure_reads(current_district_id=pos.district_id if pos else None, limit=2)
        if faction_reads:
            lines.append(f"Faction posture: {'; '.join(faction_reads)}")
        social_pressure = self._current_social_pressure_summary(pos)
        if social_pressure:
            lines.append(f"Social pressure: {social_pressure}")
        lines.append(
            "Clues: "
            f"{len(clue_objects)} total / {credible_count} credible / "
            f"{uncertain_count} uncertain / {contradicted_count} contradicted"
        )
        if clue_objects:
            lines.append(
                f"Clue picture: {self._summarize_case_clues(sorted(clue_objects, key=_clue_sort_key))}"
            )
        lines.append("")
        lines.append("Progress:")
        lines.append(f"  - Reputation: {progress.reputation.score} ({progress.reputation.tier})")
        lines.append(f"  - Access: {progress.access.score} ({progress.access.tier})")
        lines.append(f"  - Leverage: {progress.leverage.score} ({progress.leverage.tier})")
        lines.append(
            f"  - Lantern understanding: "
            f"{progress.lantern_understanding.score} ({progress.lantern_understanding.tier})"
        )
        lines.append(f"  - Clue mastery: {progress.clue_mastery.score} ({progress.clue_mastery.tier})")
        lines.append("")
        lines.append("Recovery:")
        primary_case = cases[0] if cases else None
        for step in self._global_recovery_actions(case=primary_case, pos=pos):
            lines.append(f"  - {step}")
        return "\n".join(lines)

    def clues(self) -> str:
        pos = self._load_position()
        if pos is None or not pos.clue_ids:
            return "No clues acquired yet."

        city = self._city()
        known_case_ids = set(pos.known_case_ids)
        case_titles: dict[str, str] = {}
        if city is not None:
            for cid in city.active_case_ids:
                c = self.store.load_object("CaseState", cid)
                if isinstance(c, CaseState) and cid in known_case_ids:
                    case_titles[cid] = c.title

        buckets: dict[str, list[ClueState]] = {}
        unresolved: list[str] = []
        for clue_id in pos.clue_ids:
            clue = self.store.load_object("ClueState", clue_id)
            if not isinstance(clue, ClueState):
                unresolved.append(clue_id)
                continue
            visible_case_ids = [cid for cid in clue.related_case_ids if cid in known_case_ids]
            bucket_key = visible_case_ids[0] if visible_case_ids else "__general__"
            buckets.setdefault(bucket_key, []).append(clue)

        lines = [f"=== Acquired Clues ({len(pos.clue_ids)} tracked) ==="]
        for bucket_key, bucket_clues in buckets.items():
            case_label = case_titles.get(bucket_key, "General") if bucket_key != "__general__" else "General"
            lines.append(f"\n  — {case_label} —")
            ranked_clues = sorted(bucket_clues, key=_clue_sort_key)
            for clue in ranked_clues:
                readability_tag = self._clue_readability_tag(clue)
                lines.append(f"  [{clue.reliability}] {_clue_label(clue.id)} ({clue.id})")
                lines.append(f"    Role: {readability_tag}")
                lines.append(f"    Source: {clue.source_type} / {clue.source_id.replace('_', ' ').title()}")
                lines.append(f"    {clue.clue_text}")
                implication = self._summarize_clue_implication(clue)
                if implication:
                    lines.append(f"    Why it matters: {implication}")
                next_read = self._clue_next_step(clue)
                if next_read:
                    lines.append(f"    Follow up: {next_read}")
            synthesis = self._summarize_case_clues(ranked_clues)
            if synthesis:
                lines.append(f"    Synthesis: {synthesis}")

        if unresolved:
            lines.append(f"\n  [dim] {len(unresolved)} tracked ID(s) not yet resolved:")
            for uid in unresolved:
                lines.append(f"    {uid}")
        lines.append("")
        lines.append("Next:")
        lines.append("  - board")
        lines.append("  - leads")
        lines.append("  - compare <clue_a> <clue_b>")
        return "\n".join(lines)

    def case_board(self, case_id: str | None = None) -> str:
        city = self._require_city()
        pos = self._load_position()
        case = self._resolve_case_for_board(city, pos, case_id)
        if case is None:
            return "No known active case. Use 'overview' or enter a district to pick up a lead."

        district_names = [
            district.name
            for district_id in case.involved_district_ids
            if (district := self._district(district_id)) is not None
        ]
        npc_names = [
            f"{npc.name} ({npc.id})"
            for npc_id in case.involved_npc_ids
            if (npc := self._npc(npc_id)) is not None
        ]
        case_clues = self._clues_for_case(case, pos)
        ranked_clues = sorted(case_clues, key=_clue_sort_key)
        open_questions = list(case.open_questions)
        if not open_questions:
            open_questions = [
                prompt
                for prompt in (self._clue_uncertainty_prompt(clue) for clue in ranked_clues)
                if prompt
            ]

        lines = [
            f"=== Case Board: {case.title} ===",
            f"Status: {case.status}",
            f"Pressure: {case.pressure_level}",
            f"Resolution window: {case.active_resolution_window}",
        ]
        if case.objective_summary:
            lines.append(f"Objective: {case.objective_summary}")
        if district_names:
            lines.append(f"Districts: {', '.join(district_names)}")
        if npc_names:
            lines.append(f"People: {', '.join(npc_names)}")
        if case.district_effects:
            lines.append("Signals:")
            for effect in case.district_effects[:4]:
                lines.append(f"  - {effect}")
        institutional_pressure = self._case_institutional_pressure_read(case)
        if institutional_pressure:
            lines.append(f"Institutional pressure: {institutional_pressure}")
        if open_questions:
            lines.append("Open questions:")
            for question in open_questions[:5]:
                lines.append(f"  - {question}")
        if ranked_clues:
            lines.append("Best evidence:")
            for clue in ranked_clues[:4]:
                lines.append(f"  - [{clue.reliability}] {_clue_label(clue.id)}")
                lines.append(f"    Role: {self._clue_readability_tag(clue)}")
                implication = self._summarize_clue_implication(clue)
                if implication:
                    lines.append(f"    Why it matters: {implication}")
                next_read = self._clue_next_step(clue)
                if next_read:
                    lines.append(f"    Follow up: {next_read}")
        synthesis = self._summarize_case_clues(ranked_clues)
        if synthesis:
            lines.append(f"What this suggests: {synthesis}")
        else:
            lines.append("What this suggests: You have a live case, but the evidence picture is still thin.")
        leads = self._build_lead_lines(case=case, pos=pos, limit=4)
        if leads:
            lines.append("Strongest leads:")
            for lead in leads:
                lines.append(f"  - {lead}")
        lines.append("Do next:")
        for step in self._case_recovery_actions(case=case, leads=leads):
            lines.append(f"  - {step}")
        return "\n".join(lines)

    def journal(self) -> str:
        city = self._require_city()
        pos = self._load_position()
        clues = self._load_clues([] if pos is None else pos.clue_ids)
        cases = self._known_nonlatent_cases(city, pos)
        visited_districts = [] if pos is None else pos.visited_district_ids
        district_names = [
            district.name
            for district_id in visited_districts
            if (district := self._district(district_id)) is not None
        ]
        recent_npc_events: list[str] = []
        for npc in sorted(
            [
                npc for npc in self.store.list_objects("NPCState")
                if isinstance(npc, NPCState) and npc.recent_events
            ],
            key=lambda npc: npc.updated_at,
            reverse=True,
        ):
            for event in reversed(npc.recent_events[-2:]):
                if event not in recent_npc_events:
                    recent_npc_events.append(f"{npc.name}: {event}")
                if len(recent_npc_events) >= 4:
                    break
            if len(recent_npc_events) >= 4:
                break

        lines = ["=== Journal ==="]
        if district_names:
            lines.append(f"Visited districts: {', '.join(district_names)}")
        if cases:
            lines.append("Cases in motion:")
            for case in cases[:4]:
                lines.append(f"  - {case.title}: {case.status}, pressure {case.pressure_level}")
                institutional_pressure = self._case_institutional_pressure_read(case)
                if institutional_pressure:
                    lines.append(f"    institutional pressure: {institutional_pressure}")
        if clues:
            lines.append("Evidence ledger:")
            for clue in sorted(clues, key=_clue_sort_key)[:5]:
                lines.append(
                    f"  - {_clue_label(clue.id)} [{clue.reliability}]"
                    f" from {clue.source_type}"
                )
                lines.append(f"    role: {self._clue_readability_tag(clue)}")
        if recent_npc_events:
            lines.append("Recent city movement:")
            for event in recent_npc_events:
                lines.append(f"  - {event}")
        relationship_shifts = self._recent_relationship_shifts(limit=4)
        if relationship_shifts:
            lines.append("Recent social pressure:")
            for item in relationship_shifts:
                lines.append(f"  - {item}")
        visible_case_clues = [
            clue
            for clue in clues
            if not clue.related_case_ids or any(case.id in clue.related_case_ids for case in cases)
        ]
        if visible_case_clues:
            lines.append(
                f"Current synthesis: {self._summarize_case_clues(sorted(visible_case_clues, key=_clue_sort_key))}"
            )
        lines.append("Do next:")
        primary_case = cases[0] if cases else None
        for step in self._global_recovery_actions(case=primary_case, pos=pos):
            lines.append(f"  - {step}")
        return "\n".join(lines)

    def strongest_leads(self) -> str:
        city = self._require_city()
        pos = self._load_position()
        cases = self._known_nonlatent_cases(city, pos)
        if not cases:
            return "No known active leads yet. Enter a district or talk to a local contact."
        lines = ["=== Strongest Leads ==="]
        for case in cases[:3]:
            lines.append(f"{case.title} [{case.pressure_level}]")
            case_clues = self._clues_for_case(case, pos)
            if case_clues:
                lines.append(f"  Read: {self._summarize_case_clues(sorted(case_clues, key=_clue_sort_key))}")
            for lead in self._build_lead_lines(case=case, pos=pos, limit=3):
                lines.append(f"  - {lead}")
        primary_case = cases[0]
        lines.append(
            f"What this suggests: {primary_case.title} is still the strongest active thread, and the next move should either clarify a weak clue or tighten the case picture."
        )
        lines.append("Do next:")
        for step in self._global_recovery_actions(case=primary_case, pos=pos):
            lines.append(f"  - {step}")
        return "\n".join(lines)

    def what_matters_here(self) -> str:
        city = self._require_city()
        pos = self._load_position()
        if pos is None or pos.district_id is None:
            return "You are not in a district yet. Use 'overview' to choose where to go."
        district = self._district(pos.district_id)
        if district is None:
            return f"Current district is missing: {pos.district_id}"

        lines = [f"=== What Matters Here: {district.name} ===", f"Lantern condition: {district.lantern_condition}"]
        if pos.location_id:
            location = self.store.load_object("LocationState", pos.location_id)
            if isinstance(location, LocationState):
                if location.scene_objects:
                    lines.append(f"Visible objects: {', '.join(location.scene_objects)}")
                if location.known_npc_ids:
                    npc_names = [
                        npc.name
                        for npc_id in location.known_npc_ids
                        if (npc := self._npc(npc_id)) is not None
                    ]
                    if npc_names:
                        lines.append(f"People here: {', '.join(npc_names)}")

        local_cases = [
            case
            for case in self._known_nonlatent_cases(city, pos)
            if pos.district_id in case.involved_district_ids
        ]
        if local_cases:
            lines.append("Local case pressure:")
            for case in local_cases[:3]:
                lines.append(f"  - {case.title}: {case.pressure_level}")
        social_pressure = self._current_social_pressure_summary(pos)
        if social_pressure:
            lines.append(f"Social pressure: {social_pressure}")
        standouts: list[str] = []
        for case in local_cases[:2]:
            standouts.extend(self._build_lead_lines(case=case, pos=pos, limit=2))
        if not standouts:
            standouts.append("No live contradiction is surfaced here yet; inspect a location or speak to a contact.")
        lines.append("Standouts:")
        for item in standouts[:4]:
            lines.append(f"  - {item}")
        lines.append("Do next:")
        for action in self._matters_recovery_actions(pos=pos, local_cases=local_cases):
            lines.append(f"  - {action}")
        return "\n".join(lines)

    def compare_clues(self, left_ref: str, right_ref: str) -> str:
        pos = self._load_position()
        if pos is None or not pos.clue_ids:
            return "No known clues to compare yet."
        left = self._resolve_known_clue(left_ref, pos.clue_ids)
        right = self._resolve_known_clue(right_ref, pos.clue_ids)
        if left is None:
            raise LookupError(f"Clue not found: {left_ref}")
        if right is None:
            raise LookupError(f"Clue not found: {right_ref}")
        if left.id == right.id:
            return "Choose two different clues to compare."

        shared_cases = self._shared_case_titles(left, right, set(pos.known_case_ids))
        shared_npcs = self._shared_npc_names(left, right)
        shared_districts = self._shared_district_names(left, right)
        reliability_read = self._compare_reliability(left, right)
        relation_read = self._compare_relation(left, right, set(pos.known_case_ids))

        lines = [
            f"=== Compare Clues ===",
            f"Left: {_clue_label(left.id)} [{left.reliability}]",
            f"Right: {_clue_label(right.id)} [{right.reliability}]",
            reliability_read,
            relation_read,
        ]
        if shared_cases:
            lines.append(f"Shared case context: {', '.join(shared_cases)}")
        if shared_npcs:
            lines.append(f"Shared people: {', '.join(shared_npcs)}")
        if shared_districts:
            lines.append(f"Shared districts: {', '.join(shared_districts)}")
        lines.append("Texts:")
        lines.append(f"  - {_clue_label(left.id)}: {left.clue_text}")
        lines.append(f"  - {_clue_label(right.id)}: {right.clue_text}")
        lines.append(f"Synthesis: {self._compare_synthesis(left, right, set(pos.known_case_ids))}")
        lines.append("Do next:")
        for action in self._compare_recovery_actions(
            left=left,
            right=right,
            pos=pos,
            shared_cases=shared_cases,
            shared_districts=shared_districts,
        ):
            lines.append(f"  - {action}")
        return "\n".join(lines)

    def go(self, location_id: str) -> str:
        pos = self._load_position()
        if pos is None or pos.district_id is None:
            raise LookupError("No current district. Use 'enter <district_id>' first.")
        district = self._district(pos.district_id)
        if district is None:
            raise LookupError(f"District not found: {pos.district_id}")
        if location_id not in district.visible_locations:
            raise LookupError(
                f"{location_id} is not a known location in {district.name}. "
                f"Available: {', '.join(district.visible_locations)}"
            )
        loc = self.store.load_object("LocationState", location_id)
        if not isinstance(loc, LocationState):
            raise LookupError(f"Location not found: {location_id}")
        self._save_position(location_id=location_id, npc_ids=[nid for nid in loc.known_npc_ids])
        lines = [f"→ {loc.name}  ({loc.location_type})"]
        if loc.known_npc_ids:
            npc_parts = []
            for nid in loc.known_npc_ids:
                npc = self._npc(nid)
                npc_parts.append(f"{npc.name} ({nid})" if npc else nid)
            lines.append(f"NPCs here: {', '.join(npc_parts)}")
        else:
            lines.append("NPCs here: —")
        if loc.scene_objects:
            lines.append(f"Objects: {', '.join(loc.scene_objects)}")
        if loc.clue_ids:
            lines.append(f"Clues present: {len(loc.clue_ids)}")
        lines.append("Suggested actions:")
        lines.append(f"  - inspect {location_id}")
        for nid in loc.known_npc_ids[:2]:
            lines.append(f"  - talk {nid} <question>")
        lines.append("  - matters")
        return "\n".join(lines)

    def look(self, district_id: str | None = None) -> str:
        if district_id is None:
            pos = self._load_position()
            if pos is None or pos.district_id is None:
                raise LookupError("No current district. Use 'enter <district_id>' first.")
            district_id = pos.district_id
        district = self._district(district_id)
        if district is None:
            raise LookupError(f"District not found: {district_id}")

        # Build a set of clue IDs in active cases whose involved districts include this one
        city = self._city()
        case_clue_ids: set[str] = set()
        if city:
            for cid in city.active_case_ids:
                case = self.store.load_object("CaseState", cid)
                if (
                    isinstance(case, CaseState)
                    and case.status != "latent"
                    and district_id in case.involved_district_ids
                ):
                    case_clue_ids.update(case.known_clue_ids)

        lines = [
            f"=== {district.name} ===",
            f"Lanterns: {district.lantern_condition}",
            "",
            "Locations:",
        ]
        for loc_id in district.visible_locations:
            loc = self.store.load_object("LocationState", loc_id)
            if not isinstance(loc, LocationState):
                continue
            npc_names = []
            for nid in loc.known_npc_ids:
                npc = self._npc(nid)
                if npc is not None:
                    npc_names.append(f"{npc.name} ({nid})")
            npc_str = ", ".join(npc_names) if npc_names else "—"
            clues_here = len([c for c in loc.clue_ids if c in case_clue_ids])
            clue_tag = f"  [!] {clues_here} clue(s) of interest" if clues_here else ""
            lines.append(f"  {loc.name}  ({loc_id}){clue_tag}")
            lines.append(f"    NPCs: {npc_str}")
            if loc.scene_objects:
                lines.append(f"    Objects: {', '.join(loc.scene_objects)}")
        if not district.visible_locations:
            lines.append("  None")
        local_cases = [
            case
            for case in self._known_nonlatent_cases(city, self._load_position())
            if district_id in case.involved_district_ids
        ] if city is not None else []
        if local_cases:
            lines.append("")
            lines.append("Local pressure:")
            for case in local_cases[:3]:
                lines.append(f"  - {case.title}: {case.pressure_level}")
        lines.append("")
        lines.append("Recovery:")
        lines.append("  - matters")
        lines.append("  - leads")
        return "\n".join(lines)

    def get_state_snapshot(self) -> dict[str, object]:
        city = self._require_city()
        case = self._active_case(city)
        clue = self._primary_clue()
        npc = self._npc("npc_shrine_keeper")
        progress = self._require_progress()
        lantern_condition = "unknown"
        if case is not None and case.involved_district_ids:
            district = self._district(case.involved_district_ids[0])
            if district is not None:
                lantern_condition = district.lantern_condition
        return {
            "city_id": city.id,
            "time_index": city.time_index,
            "case_status": None if case is None else case.status,
            "clue_reliability": None if clue is None else clue.reliability,
            "lantern_condition": lantern_condition,
            "npc_memory_count": 0 if npc is None else len(npc.memory_log),
            "lantern_understanding_score": progress.lantern_understanding.score,
        }

    def _load_clues(self, clue_ids: list[str]) -> list[ClueState]:
        return [
            clue
            for clue_id in clue_ids
            if isinstance(clue := self.store.load_object("ClueState", clue_id), ClueState)
        ]

    def _known_nonlatent_cases(
        self,
        city: object,
        pos: ActiveWorkingSet | None,
    ) -> list[CaseState]:
        known_ids = None if pos is None else set(pos.known_case_ids)
        cases = [
            case
            for case_id in getattr(city, "active_case_ids", [])
            if isinstance(case := self.store.load_object("CaseState", case_id), CaseState)
            and case.status != "latent"
            and (known_ids is None or case.id in known_ids)
        ]
        return sorted(cases, key=_case_sort_key)

    def _resolve_case_for_board(
        self,
        city: object,
        pos: ActiveWorkingSet | None,
        case_id: str | None,
    ) -> CaseState | None:
        if case_id is not None:
            case = self.store.load_object("CaseState", case_id)
            if isinstance(case, CaseState) and case.status != "latent":
                return case
            raise LookupError(f"Case not found: {case_id}")
        known_cases = self._known_nonlatent_cases(city, pos)
        return None if not known_cases else known_cases[0]

    def _clues_for_case(
        self,
        case: CaseState,
        pos: ActiveWorkingSet | None,
    ) -> list[ClueState]:
        known = set([] if pos is None else pos.clue_ids)
        clue_ids = [clue_id for clue_id in case.known_clue_ids if clue_id in known]
        if not clue_ids and known:
            clue_ids = [
                clue_id
                for clue_id in known
                if isinstance(clue := self.store.load_object("ClueState", clue_id), ClueState)
                and case.id in clue.related_case_ids
            ]
        return self._load_clues(clue_ids)

    def _build_lead_lines(
        self,
        *,
        case: CaseState,
        pos: ActiveWorkingSet | None,
        limit: int,
    ) -> list[str]:
        clues = self._clues_for_case(case, pos)
        lines: list[str] = []
        uncertain = [
            self._clue_uncertainty_prompt(clue)
            for clue in sorted(clues, key=_clue_sort_key)
            if clue.reliability not in _CREDIBLE_RELIABILITIES
        ]
        for prompt in uncertain:
            if prompt:
                lines.append(prompt)
            if len(lines) >= limit:
                return lines[:limit]
        for question in case.open_questions:
            if question not in lines:
                lines.append(question)
            if len(lines) >= limit:
                return lines[:limit]
        if case.involved_npc_ids and len(lines) < limit:
            npc = self._npc(case.involved_npc_ids[0])
            if npc is not None:
                lines.append(f"Talk to {npc.name} about {case.title.lower()}.")
        if case.involved_district_ids and len(lines) < limit:
            district = self._district(case.involved_district_ids[0])
            if district is not None:
                lines.append(f"Inspect a location in {district.name} tied to this case.")
        return lines[:limit]

    def _case_recovery_actions(self, *, case: CaseState, leads: list[str]) -> list[str]:
        actions: list[str] = []
        if leads:
            actions.append(leads[0])
        actions.extend(self._institutional_pressure_recovery_actions(case=case))
        if case.involved_district_ids:
            district = self._district(case.involved_district_ids[0])
            if district is not None:
                actions.append(f"Use 'matters' in {district.name} to re-check the live scene.")
        actions.append("Use 'leads' to rank the strongest unresolved thread.")
        actions.append("Use 'compare <clue_a> <clue_b>' if two clues seem related or inconsistent.")
        deduped: list[str] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)
        return deduped[:4]

    def _global_recovery_actions(
        self,
        *,
        case: CaseState | None,
        pos: ActiveWorkingSet | None,
    ) -> list[str]:
        actions: list[str] = []
        if case is not None:
            actions.extend(self._institutional_pressure_recovery_actions(case=case))
        if pos is not None and pos.location_id:
            actions.append("matters")
        if case is not None:
            actions.append(f"board {case.id}")
        actions.append("leads")
        if pos is not None and len(pos.clue_ids) >= 2:
            actions.append("compare <clue_a> <clue_b>")
        deduped: list[str] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)
        return deduped[:4]

    def _institutional_pressure_recovery_actions(self, *, case: CaseState) -> list[str]:
        institutional_pressure = self._case_institutional_pressure_read(case)
        if not institutional_pressure:
            return []

        lowered = institutional_pressure.lower()
        district_name: str | None = None
        if case.involved_district_ids:
            district = self._district(case.involved_district_ids[0])
            if district is not None:
                district_name = district.name
        npc_name: str | None = None
        if case.involved_npc_ids:
            npc = self._npc(case.involved_npc_ids[0])
            if npc is not None:
                npc_name = npc.name

        if "paper certainty" in lowered or "record trail" in lowered or "records and certification" in lowered:
            actions = [
                "Use 'compare <clue_a> <clue_b>' to catch record inconsistencies before they settle into the official version.",
            ]
            if district_name is not None:
                actions.insert(
                    0,
                    f"Use 'matters' in {district_name} to press on copies, ledgers, and corroborating records before they shift again.",
                )
            return actions

        if "constricting access" in lowered or "hardening witnesses" in lowered or "tightening official access" in lowered:
            actions: list[str] = []
            if npc_name is not None:
                actions.append(
                    f"Talk to {npc_name} before procedure hardens the witness picture any further."
                )
            if district_name is not None:
                actions.append(
                    f"Use 'matters' in {district_name} to see which people and places are still reachable before access closes."
                )
            return actions

        return []

    def _current_social_pressure_summary(self, pos: ActiveWorkingSet | None) -> str:
        if pos is None or not pos.npc_ids:
            return ""
        npc = self._npc(pos.npc_ids[0])
        if npc is None:
            return ""
        parts = [f"{npc.name} is currently {npc.offscreen_state}"]
        if npc.loyalty:
            loyalty = npc.relationships.get(npc.loyalty)
            if loyalty is not None and loyalty.status:
                parts.append(f"{npc.loyalty}: {loyalty.status}")
        player_rel = npc.relationships.get("player")
        if player_rel is not None and player_rel.status:
            parts.append(f"toward you: {player_rel.status}")
        return "; ".join(parts)

    def _recent_relationship_shifts(self, *, limit: int) -> list[str]:
        reads: list[str] = []
        for npc in sorted(
            [
                npc for npc in self.store.list_objects("NPCState")
                if isinstance(npc, NPCState) and npc.memory_log
            ],
            key=lambda npc: npc.updated_at,
            reverse=True,
        ):
            for entry in reversed(npc.memory_log[-3:]):
                if not isinstance(entry, dict) or entry.get("memory_type") != "offscreen_event":
                    continue
                if npc.loyalty:
                    loyalty = npc.relationships.get(npc.loyalty)
                    if loyalty is not None and loyalty.status:
                        reads.append(
                            f"{npc.name}: {npc.loyalty} reads as {loyalty.status} while {npc.offscreen_state}."
                        )
                        break
            if len(reads) >= limit:
                break
        return reads[:limit]

    def _faction_pressure_reads(
        self,
        *,
        current_district_id: str | None,
        limit: int,
    ) -> list[str]:
        city = self._city()
        if city is None:
            return []
        reads: list[str] = []
        for faction_id in city.faction_ids:
            faction = self.store.load_object("FactionState", faction_id)
            if not isinstance(faction, FactionState):
                continue
            target_district_id = current_district_id
            if target_district_id is None or target_district_id not in faction.influence_by_district:
                if faction.influence_by_district:
                    target_district_id = max(
                        faction.influence_by_district.items(), key=lambda item: item[1]
                    )[0]
                else:
                    target_district_id = None
            district_label = target_district_id or "the city"
            plan = faction.active_plans[0] if faction.active_plans else "holding position"
            reads.append(
                f"{faction.name}: {faction.attitude_toward_player} toward you, focused on {district_label}, "
                f"style={faction_style_label(faction)}, tactic={faction_tactic_label(faction)}, plan '{plan}'"
            )
            if len(reads) >= limit:
                break
        return reads[:limit]

    def _case_institutional_pressure_read(self, case: CaseState) -> str:
        reads: list[str] = []
        for faction_id in case.involved_faction_ids:
            faction = self.store.load_object("FactionState", faction_id)
            if not isinstance(faction, FactionState):
                continue
            style = faction_style_label(faction)
            if style == "records control" and any(
                flag.startswith("records_drift:") or flag.startswith("coverup:")
                for flag in case.offscreen_risk_flags
            ):
                reads.append(f"{faction.name} is degrading paper certainty and smothering the record trail")
            elif style == "civic enforcement" and any(
                flag.startswith("isolation:") or flag.startswith("faction_pressure:")
                for flag in case.offscreen_risk_flags
            ):
                reads.append(f"{faction.name} is constricting access and hardening witnesses through procedure")
            elif style == "civic enforcement" and any(
                effect.startswith("civic_pressure:") for effect in case.district_effects
            ):
                reads.append(f"{faction.name} is tightening official access around the case")
            elif style == "records control" and any(
                effect.startswith("coverup:") for effect in case.district_effects
            ):
                reads.append(f"{faction.name} is covering its tracks through records and certification")
        return "; ".join(reads[:2])

    def _matters_recovery_actions(
        self,
        *,
        pos: ActiveWorkingSet,
        local_cases: list[CaseState],
    ) -> list[str]:
        actions: list[str] = []
        if pos.location_id:
            actions.append(f"inspect {pos.location_id}")
        if pos.npc_ids:
            actions.append(f"talk {pos.npc_ids[0]} <question>")
        if local_cases:
            actions.append("board")
        if len(pos.clue_ids) >= 2:
            actions.append("compare <clue_a> <clue_b>")
        actions.append("leads")
        deduped: list[str] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)
        return deduped[:4]

    def _summarize_case_clues(self, clues: list[ClueState]) -> str:
        if not clues:
            return ""
        credible = [clue for clue in clues if clue.reliability in _CREDIBLE_RELIABILITIES]
        contradicted = [clue for clue in clues if clue.reliability == "contradicted"]
        uncertain = [clue for clue in clues if clue.reliability not in _CREDIBLE_RELIABILITIES and clue.reliability != "contradicted"]
        parts: list[str] = []
        if credible:
            parts.append(f"{len(credible)} clue(s) currently support the case theory")
        if uncertain:
            parts.append(f"{len(uncertain)} still need confirmation")
        if contradicted:
            parts.append(f"{len(contradicted)} are actively in conflict")
        return "; ".join(parts)

    def _summarize_clue_implication(self, clue: ClueState) -> str:
        if clue.reliability in {"solid", "credible"}:
            if clue.related_case_ids:
                return "This currently supports the strongest case theory you can defend."
            return "This is credible enough to anchor a broader theory, even if no case is attached yet."
        if clue.reliability == "contradicted":
            return "This actively clashes with the current picture and could break a bad theory open."
        if clue.source_type == "testimony":
            return "This is a live lead, but it is still testimony. You need a person, record, or second witness to steady it."
        if clue.source_type == "document":
            return "This points at a paper trail worth checking, but it still needs corroboration before it should drive a conclusion."
        return "This is a follow-up lead rather than a conclusion. Treat it as something to test."

    def _clue_readability_tag(self, clue: ClueState) -> str:
        if clue.reliability == "contradicted":
            return "contradiction to explain"
        if clue.reliability in _CREDIBLE_RELIABILITIES:
            if clue.related_case_ids:
                return "supports current case"
            return "credible free-standing lead"
        if clue.source_type == "testimony":
            return "lead to verify"
        if clue.source_type == "document":
            return "paper trail to test"
        return "possible follow-up"

    def _clue_next_step(self, clue: ClueState) -> str:
        if clue.reliability == "contradicted":
            return self._clue_uncertainty_prompt(clue)
        if clue.reliability in _CREDIBLE_RELIABILITIES:
            if clue.related_case_ids:
                return "Use this in board or compare to see what it strengthens."
            return "Keep this in mind when a case or second clue lines up with it."
        return self._clue_uncertainty_prompt(clue)

    def _clue_uncertainty_prompt(self, clue: ClueState) -> str:
        label = _clue_label(clue.id)
        if clue.reliability == "contradicted":
            return f"Resolve why {label.lower()} is contradicted before relying on it."
        if clue.reliability not in _CREDIBLE_RELIABILITIES:
            if clue.related_npc_ids:
                npc = self._npc(clue.related_npc_ids[0])
                if npc is not None:
                    return f"Ask {npc.name} to clarify {label.lower()}."
            return f"Corroborate {label.lower()} with a second source."
        return ""

    def _resolve_known_clue(self, raw: str, known_ids: list[str]) -> ClueState | None:
        clue_map = {
            clue_id: clue
            for clue_id in known_ids
            if isinstance(clue := self.store.load_object("ClueState", clue_id), ClueState)
        }
        if raw in clue_map:
            return clue_map[raw]
        normalized = raw.lower().replace("_", " ").replace("-", " ")
        best: ClueState | None = None
        best_score = 0
        for clue in clue_map.values():
            label = _clue_label(clue.id).lower()
            source = clue.source_id.lower().replace("_", " ")
            score = 0
            if normalized in label or label in normalized:
                score += 3
            if normalized in source or source in normalized:
                score += 2
            score += len(set(normalized.split()) & set(label.split()))
            if score > best_score:
                best = clue
                best_score = score
        return best if best_score > 0 else None

    def _shared_case_titles(
        self,
        left: ClueState,
        right: ClueState,
        known_case_ids: set[str],
    ) -> list[str]:
        return [
            case.title
            for case_id in sorted((set(left.related_case_ids) & set(right.related_case_ids)) & known_case_ids)
            if isinstance(case := self.store.load_object("CaseState", case_id), CaseState)
        ]

    def _shared_npc_names(self, left: ClueState, right: ClueState) -> list[str]:
        return [
            npc.name
            for npc_id in sorted(set(left.related_npc_ids) & set(right.related_npc_ids))
            if (npc := self._npc(npc_id)) is not None
        ]

    def _shared_district_names(self, left: ClueState, right: ClueState) -> list[str]:
        return [
            district.name
            for district_id in sorted(set(left.related_district_ids) & set(right.related_district_ids))
            if (district := self._district(district_id)) is not None
        ]

    def _compare_reliability(self, left: ClueState, right: ClueState) -> str:
        if left.reliability == right.reliability:
            return f"Reliability: both clues currently read as {left.reliability}."
        if left.reliability in _CREDIBLE_RELIABILITIES and right.reliability not in _CREDIBLE_RELIABILITIES:
            return f"Reliability: {_clue_label(left.id)} is the stronger anchor; {_clue_label(right.id)} still needs support."
        if right.reliability in _CREDIBLE_RELIABILITIES and left.reliability not in _CREDIBLE_RELIABILITIES:
            return f"Reliability: {_clue_label(right.id)} is the stronger anchor; {_clue_label(left.id)} still needs support."
        return f"Reliability: {left.reliability} versus {right.reliability}."

    def _compare_relation(self, left: ClueState, right: ClueState, known_case_ids: set[str]) -> str:
        shared_cases = (set(left.related_case_ids) & set(right.related_case_ids)) & known_case_ids
        shared_districts = set(left.related_district_ids) & set(right.related_district_ids)
        if shared_cases and shared_districts:
            return "Relation: these clues point into the same investigation and the same local context."
        if shared_cases:
            return "Relation: these clues belong to the same case, but they come from different contexts."
        if shared_districts:
            return "Relation: these clues describe the same district pressure from different angles."
        return "Relation: these clues are not directly linked; compare them carefully before building a theory."

    def _compare_synthesis(self, left: ClueState, right: ClueState, known_case_ids: set[str]) -> str:
        if left.reliability == "contradicted" or right.reliability == "contradicted":
            return "One of these clues is already in conflict. Explain that contradiction before treating them as a shared theory."
        if (set(left.related_case_ids) & set(right.related_case_ids)) & known_case_ids:
            if left.reliability in _CREDIBLE_RELIABILITIES and right.reliability in _CREDIBLE_RELIABILITIES:
                return "Together, these clues can support a stronger case interpretation."
            return "These clues belong together, but at least one still needs corroboration before it should drive a conclusion."
        if set(left.related_district_ids) & set(right.related_district_ids):
            return "These clues may reveal district pattern rather than direct causation. Use them to test pressure, not just sequence."
        return "These clues are better treated as parallel signals until a case, district, or NPC ties them together."

    def _compare_recovery_actions(
        self,
        *,
        left: ClueState,
        right: ClueState,
        pos: ActiveWorkingSet,
        shared_cases: list[str],
        shared_districts: list[str],
    ) -> list[str]:
        actions: list[str] = []
        if shared_cases:
            actions.append("board")
        stronger: ClueState | None = None
        weaker: ClueState | None = None
        if left.reliability in _CREDIBLE_RELIABILITIES and right.reliability not in _CREDIBLE_RELIABILITIES:
            stronger, weaker = left, right
        elif right.reliability in _CREDIBLE_RELIABILITIES and left.reliability not in _CREDIBLE_RELIABILITIES:
            stronger, weaker = right, left
        if stronger is not None and weaker is not None:
            label = _clue_label(stronger.id).lower()
            if weaker.related_npc_ids:
                actions.append(f"talk {weaker.related_npc_ids[0]} about why {label} and {_clue_label(weaker.id).lower()} do not line up yet")
            else:
                actions.append(f"Treat {_clue_label(stronger.id)} as the anchor and test {_clue_label(weaker.id).lower()} against a second source.")
        elif left.reliability == "contradicted" or right.reliability == "contradicted":
            contradicted = left if left.reliability == "contradicted" else right
            if contradicted.related_npc_ids:
                actions.append(f"talk {contradicted.related_npc_ids[0]} about why {_clue_label(contradicted.id).lower()} breaks down")
            else:
                actions.append(f"Find a second source before relying on {_clue_label(contradicted.id).lower()}.")
        if shared_districts and pos.district_id is not None:
            current_district = self._district(pos.district_id)
            if current_district is not None and current_district.name in shared_districts:
                actions.append("matters")
        if not actions:
            actions.append("leads")
        actions.append("compare <clue_a> <clue_b>")
        deduped: list[str] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)
        return deduped[:4]

    def _propagate_missingness(
        self,
        city: object,
        district: DistrictState,
        *,
        updated_at: str,
    ) -> list[str]:
        """Degrade vulnerable clues when missingness conditions are met.

        Fires when: pressure is medium/high + lantern is strained + unresolved contradiction exists.
        Physical clues are immune. Testimony degrades first; documents follow at high pressure.
        Returns player-facing notices for any clues that worsened.
        """
        pressure_level = _missingness_level(getattr(city, "missingness_pressure", 0.0))
        if pressure_level not in {"medium", "high"}:
            return []
        if district.lantern_condition not in {"dim", "flickering", "extinguished", "altered"}:
            return []

        clues = [
            obj
            for clue_id in _CASE_CLUE_IDS
            if isinstance(obj := self.store.load_object("ClueState", clue_id), ClueState)
        ]

        # Propagation only fires when an unresolved contradiction exists in the case
        if not any(c.reliability == "contradicted" for c in clues):
            return []

        degraded: list[ClueState] = []
        notices: list[str] = []

        for clue in clues:
            if clue.reliability not in {"uncertain", "unstable"}:
                continue
            if clue.source_type == "physical":
                continue  # Physical evidence resists propagation

            # Testimony degrades under medium+ pressure; documents only under high
            should_degrade = (
                pressure_level == "high"
                or (pressure_level == "medium" and clue.source_type == "testimony")
            )

            if should_degrade and clue.reliability == "uncertain":
                degraded.append(
                    clue.model_copy(update={"reliability": "unstable", "updated_at": updated_at})
                )
                notices.append(
                    f"[Pressure: {_clue_label(clue.id)} is drifting - reliability now unstable]"
                )

        if degraded:
            self.store.save_objects_atomically(degraded)

        # Under severe conditions (flickering+), increase city pressure slightly
        if district.lantern_condition in {"flickering", "extinguished"} and pressure_level == "medium":
            new_pressure = min(1.0, getattr(city, "missingness_pressure", 0.0) + 0.05)
            updated_city = city.model_copy(  # type: ignore[union-attr]
                update={"missingness_pressure": new_pressure, "updated_at": updated_at}
            )
            self.store.save_object(updated_city)

        return notices

    def _maybe_transient_encounter(
        self,
        district_id: str,
        district: DistrictState,
        *,
        updated_at: str,
    ) -> str | None:
        """Roll for a transient NPC encounter; return formatted text or None."""
        encounter = roll_encounter(district_id)
        if encounter is None:
            return None

        # Apply any mechanical effect
        if encounter.effect_track and encounter.effect_amount != 0:
            progress = self._require_progress()
            progress, _ = apply_progress_change(
                progress,
                track=encounter.effect_track,
                amount=encounter.effect_amount,
                reason=encounter.effect_reason,
                updated_at=updated_at,
            )
            self.store.save_object(progress)

        # Enrich narrative with LLM when available
        if self.llm_config is not None:
            city = self._require_city()
            llm_client = OpenAICompatibleLLMClient(self.llm_config)
            try:
                result = generate_transient_encounter(
                    archetype=encounter.archetype,
                    district_name=district.name,
                    lantern_condition=district.lantern_condition,
                    global_tension=city.global_tension,
                    llm_client=llm_client,
                )
                narrative = result.narrative
                if result.spoken_line:
                    narrative = f"{narrative}\n  \"{result.spoken_line}\""
            except TransientGenerationError:
                narrative = encounter.narrative
        else:
            narrative = encounter.narrative

        return f"[Passing: {encounter.archetype}]\n{narrative}"

    def _check_case_discovery(self, district_id: str, *, updated_at: str) -> str | None:
        """Ambient world traversal does not introduce cases.

        Cases must be surfaced explicitly through a hook NPC / contextual GM framing,
        not by merely inspecting a relevant district or location.
        """
        log.debug("_check_case_discovery disabled district=%r", district_id)
        return None

    def _check_npc_case_hook(self, npc_id: str, *, updated_at: str) -> str | None:
        """Activate a latent case when the player talks to its hook NPC.

        Returns a formatted narrative hook string, or None if this NPC introduces no case.
        """
        city = self._require_city()
        for case_id in city.active_case_ids:
            case = self.store.load_object("CaseState", case_id)
            if not isinstance(case, CaseState):
                continue
            if case.status != "latent":
                continue
            if case.hook_npc_id != npc_id:
                continue
            updated_case = transition_case(case, "active", updated_at=updated_at)
            self.store.save_object(updated_case)
            hook_text = case.discovery_hook or f"Something about this case demands your attention: {case.title}"
            return f"[New case: {case.title}]\n{hook_text}"
        return None

    def _peek_npc_case_hook(self, npc_id: str) -> tuple[CaseState | None, str | None]:
        """Look up any latent case this NPC introduces — without activating it.

        Returns (case, discovery_hook_text) so the caller can pass the hook text to the
        LLM before dialogue is generated, then activate the case afterwards.
        """
        city = self._require_city()
        for case_id in city.active_case_ids:
            case = self.store.load_object("CaseState", case_id)
            if not isinstance(case, CaseState):
                continue
            if case.status != "latent":
                continue
            if case.hook_npc_id != npc_id:
                continue
            hook_text = case.discovery_hook or None
            return case, hook_text
        return None, None

    def _generate_latent_cases(self, count: int = 2) -> None:
        """Call the LLM to generate new latent cases and bootstrap them into the world."""
        if self.llm_config is None:
            return
        city = self._require_city()
        factions = [
            obj
            for fid in city.faction_ids
            if isinstance(obj := self.store.load_object("FactionState", fid), FactionState)
        ]
        districts = [
            obj
            for did in city.district_ids
            if isinstance(obj := self.store.load_object("DistrictState", did), DistrictState)
        ]
        progress = self._require_progress()
        all_cases = self.store.list_objects("CaseState")
        existing_cases = [c for c in all_cases if isinstance(c, CaseState)]
        existing_case_types = [c.case_type for c in existing_cases]
        all_npcs = self.store.list_objects("NPCState")
        existing_npc_names = [npc.name for npc in all_npcs if isinstance(npc, NPCState)]
        gen_case_count = sum(
            1 for c in existing_cases if c.id.startswith("case_gen_")
        )
        llm_client = OpenAICompatibleLLMClient(self.llm_config)
        generator = CaseGenerator(llm_client)
        for i in range(count):
            request = CaseGenerationRequest(
                request_id=f"req_gen_{gen_case_count + i:04d}",
                city=city,
                factions=factions,
                districts=districts,
                progress=progress,
                existing_case_types=existing_case_types,
                existing_npc_names=existing_npc_names,
            )
            try:
                result = generator.generate(request)
            except CaseGenerationError:
                continue
            city = self._require_city()
            bootstrap_result = bootstrap_generated_case(
                result,
                store=self.store,
                city=city,
                case_index=gen_case_count + i,
                updated_at=TURN_ZERO,
            )
            self.store.save_objects_atomically(
                [
                    bootstrap_result.case,
                    *bootstrap_result.npcs,
                    *bootstrap_result.clues,
                    *bootstrap_result.updated_locations,
                    *bootstrap_result.updated_districts,
                    bootstrap_result.updated_city,
                ]
            )
            city = bootstrap_result.updated_city
            existing_case_types.append(result.case_type)
            existing_npc_names.extend(spec.name for spec in result.npc_specs)

    def _generate_city_seed(
        self,
        concept: str | None = None,
        on_progress: Callable[[str], None] | None = None,
    ):
        """Use the LLM to generate a new CitySeedDocument."""
        from lantern_city.llm_client import OpenAICompatibleLLMClient
        assert self.llm_config is not None
        llm = OpenAICompatibleLLMClient(self.llm_config)
        generator = CitySeedGenerator(llm)
        request = CitySeedGenerationRequest(
            request_id="seed_gen_new",
            concept=concept or "",
        )
        try:
            return generator.generate(request, on_progress=on_progress)
        except CitySeedGenerationError as exc:
            raise RuntimeError(f"City seed generation failed: {exc}") from exc

    def _generate_world_content(self, on_progress: Callable[[str], None] | None = None) -> None:
        """Use the LLM to generate locations, clues, and NPC placements for the current city."""
        from lantern_city.llm_client import OpenAICompatibleLLMClient
        assert self.llm_config is not None
        city = self._require_city()
        districts = [
            obj for did in city.district_ids
            if (obj := self.store.load_object("DistrictState", did)) is not None
            and isinstance(obj, DistrictState)
        ]
        npcs = self.store.list_objects("NPCState")
        npcs = [n for n in npcs if isinstance(n, NPCState)]
        cases = [
            obj for cid in city.active_case_ids
            if (obj := self.store.load_object("CaseState", cid)) is not None
            and isinstance(obj, CaseState)
        ]
        llm = OpenAICompatibleLLMClient(self.llm_config)
        generator = WorldContentGenerator(llm)
        content = generator.generate(
            districts=districts,
            npcs=npcs,
            cases=cases,
            on_progress=on_progress,
        )
        objects_to_save: list = (
            content.locations
            + content.clues
            + content.district_updates
            + content.npc_updates
            + content.case_updates
        )
        self.store.save_objects_atomically(objects_to_save)

    def _activate_authored_start_case(self) -> None:
        case = self.store.load_object("CaseState", "case_missing_clerk")
        if not isinstance(case, CaseState) or case.status != "latent":
            return
        activated = transition_case(case, "active", updated_at=TURN_ZERO)
        self.store.save_object(activated)
        self._introduce_case(case.id)

    def _resolved_startup_mode(self) -> str:
        """Resolve whether startup uses the authored baseline or generated runtime."""
        if self.startup_mode == "auto":
            return "generated_runtime" if self.llm_config is not None else "mvp_baseline"
        if self.startup_mode == "mvp_baseline":
            return "mvp_baseline"
        if self.startup_mode == "generated_runtime":
            if self.llm_config is None:
                raise ValueError("startup_mode='generated_runtime' requires llm_config")
            return "generated_runtime"
        raise ValueError(f"Unsupported startup_mode: {self.startup_mode}")

    def _probe_llm_quality(self) -> str:
        assert self.llm_config is not None
        client = OpenAICompatibleLLMClient(self.llm_config)
        started_at = perf_counter()
        try:
            payload = client.generate_json(
                messages=_model_probe_messages(),
                temperature=0.1,
                max_tokens=600,
                schema=_MODEL_QUALITY_PROBE_SCHEMA,
            )
            elapsed = perf_counter() - started_at
            result = NPCResponseGenerationResult.model_validate(payload)
        except Exception as exc:
            log.warning("llm quality probe failed: %s", exc)
            return (
                "Model check: warning — startup probe failed, so NPC generation quality is uncertain. "
                "You may see template fallback text."
            )
        finally:
            client.close()

        if elapsed > 20.0:
            return (
                f"Model check: warning — startup probe validated the response schema, "
                f"but it took {elapsed:.1f}s. Expect slow NPC turns."
            )
        if result.confidence < 0.35:
            return (
                "Model check: warning — startup probe returned a low-confidence NPC response. "
                "Conversation quality may be weak."
            )
        return f"Model check: pass — startup probe validated NPC response quality in {elapsed:.1f}s."

    def _seed_authored_scene_objects(self) -> None:
        old_quarter = self._district("district_old_quarter")
        lantern_ward = self._district("district_lantern_ward")
        the_docks = self._district("district_the_docks")
        market_spires = self._district("district_market_spires")
        salt_barrens = self._district("district_salt_barrens")
        underways = self._district("district_underways")
        shrine_keeper = self._npc("npc_shrine_keeper")
        archive_clerk = self._npc("npc_archive_clerk")
        brin_hesse = self._npc("npc_brin_hesse")
        tovin_vale = self._npc("npc_tovin_vale")
        sister_calis = self._npc("npc_sister_calis")
        watcher_pell = self._npc("npc_watcher_pell")
        dockmaster = self._npc("npc_dockmaster")
        dock_hauler = self._npc("npc_dock_hauler")
        records_broker = self._npc("npc_records_broker")
        guild_steward = self._npc("npc_guild_steward")
        salvage_worker = self._npc("npc_salvage_worker")
        route_warden = self._npc("npc_route_warden")
        if (
            old_quarter is None
            or lantern_ward is None
            or the_docks is None
            or market_spires is None
            or salt_barrens is None
            or underways is None
            or shrine_keeper is None
            or archive_clerk is None
            or brin_hesse is None
            or tovin_vale is None
            or sister_calis is None
            or watcher_pell is None
            or dockmaster is None
            or dock_hauler is None
            or records_broker is None
            or guild_steward is None
            or salvage_worker is None
            or route_warden is None
        ):
            raise LookupError("Bootstrap did not create required authored objects")

        # --- Locations ---
        shrine_lane = LocationState(
            id="location_shrine_lane",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Shrine Lane",
            location_type="shrine",
            known_npc_ids=[shrine_keeper.id],
            clue_ids=["clue_missing_clerk_ledgers", "clue_outage_predates_disappearance", "clue_heat_scoring_on_bracket"],
            scene_objects=["lantern bracket", "offering ledger", "shrine workroom door"],
        )
        archive_steps = LocationState(
            id="location_archive_steps",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Archive Steps",
            location_type="archive",
            known_npc_ids=[archive_clerk.id],
            clue_ids=["clue_family_record_discrepancy"],
            scene_objects=["registry board", "ledger shelf", "archive entrance log"],
        )
        ledger_room = LocationState(
            id="location_ledger_room",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Ledger Room",
            location_type="records",
            known_npc_ids=[archive_clerk.id],
            clue_ids=["clue_missing_maintenance_line"],
            scene_objects=["maintenance log shelf", "sealed inkwell", "service ledger"],
        )
        maintenance_route = LocationState(
            id="location_maintenance_route",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Maintenance Route",
            location_type="service passage",
            known_npc_ids=[brin_hesse.id],
            scene_objects=["soot-marked archway", "lantern mounting", "service key rack"],
        )
        service_passage = LocationState(
            id="location_service_passage",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Service Passage",
            location_type="service passage",
            known_npc_ids=[brin_hesse.id],
            clue_ids=["clue_hidden_copy_sheet"],
            scene_objects=["service latch", "unauthorized tool marks", "narrow passage deeper"],
        )
        subarchive_chamber = LocationState(
            id="location_subarchive_chamber",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Subarchive Chamber",
            location_type="hidden chamber",
            known_npc_ids=[tovin_vale.id],
            scene_objects=["collapsed shelving", "copied registry fragments", "broken lantern housing"],
        )
        lantern_square = LocationState(
            id="location_lantern_square",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=lantern_ward.id,
            name="Lantern Square",
            location_type="civic",
            scene_objects=["public lantern post", "civic notice board", "marked paving stones"],
        )
        regulation_office = LocationState(
            id="location_regulation_office",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=lantern_ward.id,
            name="Office of Lantern Regulation",
            location_type="administrative office",
            scene_objects=["polished counter", "bright lamp array", "compliance ledger", "precise signage"],
        )
        ceremonial_walk = LocationState(
            id="location_ceremonial_walk",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=lantern_ward.id,
            name="Ceremonial Walk",
            location_type="public thoroughfare",
            scene_objects=["evenly spaced lantern post", "reflective paving stone", "civic banner", "marked observation post"],
        )
        shrine_liaison_hall = LocationState(
            id="location_shrine_liaison_hall",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=lantern_ward.id,
            name="Shrine Liaison Hall",
            location_type="ritual annex",
            known_npc_ids=[sister_calis.id],
            clue_ids=["clue_ritual_authorization"],
            scene_objects=["polished stone floor", "controlled incense stand", "ceremonial record case", "approval seal press"],
        )
        civic_watch_desk = LocationState(
            id="location_civic_watch_desk",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=lantern_ward.id,
            name="Civic Watch Desk",
            location_type="complaint office",
            known_npc_ids=[watcher_pell.id],
            clue_ids=["clue_official_closure_order"],
            scene_objects=["complaint ledger", "stamped forms", "orderly bench row", "case archive shelf"],
        )

        # --- The Docks locations ---
        pier_landing = LocationState(
            id="location_pier_landing",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=the_docks.id,
            name="Pier Landing",
            location_type="transit dock",
            scene_objects=["mooring post", "cargo manifest board", "oil-stained rope coil"],
        )
        harbormaster_office = LocationState(
            id="location_harbormaster_office",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=the_docks.id,
            name="Harbormaster Office",
            location_type="administrative office",
            known_npc_ids=[dockmaster.id],
            scene_objects=["cargo register", "berthing chart", "damp inspection ledger"],
        )
        cargo_holding = LocationState(
            id="location_cargo_holding",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=the_docks.id,
            name="Cargo Holding",
            location_type="storage",
            known_npc_ids=[dock_hauler.id],
            scene_objects=["stacked crates", "chalk lot markings", "iron transit seal"],
        )
        dock_workers_passage = LocationState(
            id="location_dock_workers_passage",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=the_docks.id,
            name="Dock Workers Passage",
            location_type="service passage",
            scene_objects=["unmarked door", "soot-marked wall", "discarded route slip"],
        )

        # --- Market Spires locations ---
        trade_floor = LocationState(
            id="location_trade_floor",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=market_spires.id,
            name="Trade Floor",
            location_type="market",
            scene_objects=["merchant stall", "price board", "public lantern column"],
        )
        records_office = LocationState(
            id="location_records_office",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=market_spires.id,
            name="Records Office",
            location_type="administrative office",
            known_npc_ids=[records_broker.id],
            scene_objects=["transaction ledger", "filing press", "ink-stained counter"],
        )
        guild_hall = LocationState(
            id="location_guild_hall",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=market_spires.id,
            name="Guild Hall",
            location_type="authority hall",
            known_npc_ids=[guild_steward.id],
            scene_objects=["charter display", "guild seal press", "members register"],
        )
        back_counter = LocationState(
            id="location_back_counter",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=market_spires.id,
            name="Back Counter",
            location_type="restricted office",
            scene_objects=["unmarked ledger stack", "curtained access door", "sealed correspondence tray"],
        )

        # --- Salt Barrens locations ---
        abandoned_works = LocationState(
            id="location_abandoned_works",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=salt_barrens.id,
            name="Abandoned Works",
            location_type="industrial ruin",
            scene_objects=["collapsed beam stack", "salt-crusted floor", "stripped lantern mount"],
        )
        salvage_yard = LocationState(
            id="location_salvage_yard",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=salt_barrens.id,
            name="Salvage Yard",
            location_type="outdoor salvage",
            known_npc_ids=[salvage_worker.id],
            scene_objects=["sorted scrap pile", "broken glass heap", "hand-drawn boundary marker"],
        )
        lantern_graveyard = LocationState(
            id="location_lantern_graveyard",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=salt_barrens.id,
            name="Lantern Graveyard",
            location_type="decommissioned site",
            scene_objects=["rows of dead lantern casings", "corroded bracket pile", "unlit ceremonial post"],
        )

        # --- Underways locations ---
        junction_hall = LocationState(
            id="location_junction_hall",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=underways.id,
            name="Junction Hall",
            location_type="maintenance junction",
            known_npc_ids=[route_warden.id],
            scene_objects=["junction lantern array", "route marker board", "maintenance tool alcove", "district branch seals"],
        )
        conduit_run = LocationState(
            id="location_conduit_run",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=underways.id,
            name="Conduit Run",
            location_type="maintenance passage",
            scene_objects=["worn stone conduit floor", "rerouted lantern housing", "transit mark series", "access ladder rungs"],
        )
        alteration_chamber = LocationState(
            id="location_alteration_chamber",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=underways.id,
            name="Alteration Chamber",
            location_type="infrastructure node",
            scene_objects=["exposed lantern conduit junction", "modification tool set", "fresh and old work marks", "faction maintenance notation"],
        )

        # --- Clues ---
        clue_a = ClueState(
            id="clue_missing_clerk_ledgers",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="document",
            source_id=shrine_lane.id,
            clue_text=(
                "Ledger initials near the missing clerk's route do not match the public register."
            ),
            reliability="credible",
            related_npc_ids=[shrine_keeper.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_c = ClueState(
            id="clue_heat_scoring_on_bracket",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="physical",
            source_id=shrine_lane.id,
            clue_text=(
                "The lantern bracket at Shrine Lane shows heat scoring inconsistent "
                "with routine wear — the damage pattern indicates deliberate adjustment, "
                "not neglect or failure."
            ),
            reliability="credible",
            related_npc_ids=[shrine_keeper.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_b = ClueState(
            id="clue_outage_predates_disappearance",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="testimony",
            source_id=shrine_lane.id,
            clue_text=(
                "The lantern near the archive was failing before Tovin Vale "
                "was officially reported missing."
            ),
            reliability="uncertain",
            related_npc_ids=[shrine_keeper.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_e = ClueState(
            id="clue_family_record_discrepancy",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="document",
            source_id=archive_steps.id,
            clue_text=(
                "A family entry in the civic register has been edited in the same "
                "archival section where Tovin Vale's name is inconsistent — "
                "suggesting the altered lantern field was used to distort more than one record."
            ),
            reliability="contradicted",
            related_npc_ids=[archive_clerk.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_g = ClueState(
            id="clue_witness_instability",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="composite",
            source_id=old_quarter.id,
            clue_text=(
                "Accounts of Tovin Vale's last movements conflict specifically among "
                "witnesses who were near the affected lantern — those further away "
                "agree, suggesting the inconsistency is spatially bounded, not social rumor."
            ),
            reliability="uncertain",
            related_npc_ids=[shrine_keeper.id, archive_clerk.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_d = ClueState(
            id="clue_missing_maintenance_line",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="document",
            source_id=ledger_room.id,
            clue_text=(
                "A maintenance visit to the archive lantern has been removed "
                "or rewritten in the official service record."
            ),
            reliability="uncertain",
            related_npc_ids=[brin_hesse.id, archive_clerk.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_f = ClueState(
            id="clue_hidden_copy_sheet",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="physical",
            source_id=service_passage.id,
            clue_text=(
                "A handwritten copy of the altered registry entry, hidden behind the service latch. "
                "The hand matches Tovin Vale's known script — he knew the edit was deliberate "
                "and tried to preserve the original before disappearing."
            ),
            reliability="uncertain",
            related_npc_ids=[tovin_vale.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_h = ClueState(
            id="clue_official_closure_order",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="document",
            source_id=civic_watch_desk.id,
            clue_text=(
                "A pre-drafted administrative closure order for the Old Quarter lantern incident — "
                "dated before the official complaint was filed. "
                "The case was being administratively closed before it was formally opened."
            ),
            reliability="uncertain",
            related_npc_ids=[watcher_pell.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[lantern_ward.id],
        )
        clue_i = ClueState(
            id="clue_ritual_authorization",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="testimony",
            source_id=shrine_liaison_hall.id,
            clue_text=(
                "Sister Calis acknowledges that a lantern alteration of this type requires "
                "shrine-level authorization — whoever acted did so with knowledge of ritual protocols, "
                "not merely technical access."
            ),
            reliability="uncertain",
            related_npc_ids=[sister_calis.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[lantern_ward.id, old_quarter.id],
        )

        # --- District updates ---
        updated_old_quarter = old_quarter.model_copy(
            update={
                "visible_locations": [
                    shrine_lane.id,
                    archive_steps.id,
                    ledger_room.id,
                    maintenance_route.id,
                    service_passage.id,
                ],
                "hidden_locations": [subarchive_chamber.id],
                "version": old_quarter.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_lantern_ward = lantern_ward.model_copy(
            update={
                "visible_locations": [
                    lantern_square.id,
                    regulation_office.id,
                    ceremonial_walk.id,
                    shrine_liaison_hall.id,
                    civic_watch_desk.id,
                ],
                "version": lantern_ward.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_the_docks = the_docks.model_copy(
            update={
                "visible_locations": [
                    pier_landing.id,
                    harbormaster_office.id,
                    cargo_holding.id,
                ],
                "hidden_locations": [dock_workers_passage.id],
                "version": the_docks.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_market_spires = market_spires.model_copy(
            update={
                "visible_locations": [
                    trade_floor.id,
                    records_office.id,
                    guild_hall.id,
                ],
                "hidden_locations": [back_counter.id],
                "version": market_spires.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_salt_barrens = salt_barrens.model_copy(
            update={
                "visible_locations": [
                    abandoned_works.id,
                    salvage_yard.id,
                ],
                "hidden_locations": [lantern_graveyard.id],
                "version": salt_barrens.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_underways = underways.model_copy(
            update={
                "visible_locations": [
                    junction_hall.id,
                    conduit_run.id,
                ],
                "hidden_locations": [alteration_chamber.id],
                "version": underways.version + 1,
                "updated_at": TURN_ZERO,
            }
        )

        # --- NPC updates with cast-sheet values ---
        updated_shrine_keeper = shrine_keeper.model_copy(
            update={
                "public_identity": "shrine keeper",
                "hidden_objective": (
                    "Avoid exposing how much she knows about the lantern alteration. "
                    "Prevent blame from falling entirely on the shrine."
                ),
                "current_objective": (
                    "Keep the local lantern from destabilizing further. "
                    "See the truth handled by someone more capable than the archive office."
                ),
                "trust_in_player": 0.25,
                "suspicion": 0.4,
                "fear": 0.4,
                "known_clue_ids": [clue_a.id, clue_b.id, clue_c.id, clue_g.id],
                "version": shrine_keeper.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_archive_clerk = archive_clerk.model_copy(
            update={
                "public_identity": "acting archive registrar",
                "hidden_objective": (
                    "Keep the incident from becoming a scandal. "
                    "Avoid superiors discovering how compromised local records became."
                ),
                "current_objective": (
                    "Preserve archive credibility. Contain the records discrepancy."
                ),
                "trust_in_player": 0.1,
                "suspicion": 0.55,
                "fear": 0.4,
                "known_clue_ids": [clue_d.id, clue_e.id],
                "version": archive_clerk.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_brin_hesse = brin_hesse.model_copy(
            update={
                "public_identity": "lamplighter's assistant",
                "hidden_objective": (
                    "Cover for a paid errand that moved a maintenance key at the wrong time."
                ),
                "current_objective": (
                    "Avoid punishment from both the council and local maintenance crews."
                ),
                "trust_in_player": 0.3,
                "suspicion": 0.7,
                "fear": 0.8,
                "known_clue_ids": [clue_d.id],
                "version": brin_hesse.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_tovin_vale = tovin_vale.model_copy(
            update={
                "public_identity": "registry clerk, officially missing",
                "hidden_objective": (
                    "Survive. Be found by someone who will act on what they find, "
                    "not suppress it further."
                ),
                "current_objective": (
                    "Wait. The copy sheet is hidden. If someone reaches the passage, "
                    "they can find it. If they reach this chamber, they can hear the full account."
                ),
                "trust_in_player": 0.0,
                "suspicion": 0.85,
                "fear": 0.95,
                "known_clue_ids": [clue_f.id],
                "version": tovin_vale.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_sister_calis = sister_calis.model_copy(
            update={
                "public_identity": "shrine liaison to the Council of Lights",
                "hidden_objective": (
                    "Contain the ritual interpretation of the lantern alteration. "
                    "Prevent it becoming a public spiritual crisis."
                ),
                "current_objective": (
                    "Monitor how far the investigation reaches into official channels. "
                    "Manage the contact between shrine practice and civic authority."
                ),
                "trust_in_player": 0.1,
                "suspicion": 0.5,
                "fear": 0.2,
                "known_clue_ids": [clue_i.id],
                "version": sister_calis.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_watcher_pell = watcher_pell.model_copy(
            update={
                "public_identity": "civic watch compliance officer",
                "hidden_objective": (
                    "Close the missing clerk file without formal investigation. "
                    "Preserve district calm and watch standing."
                ),
                "current_objective": (
                    "Maintain watch posture. Keep complaints at the administrative level. "
                    "Prevent escalation to civic inquiry."
                ),
                "trust_in_player": 0.05,
                "suspicion": 0.35,
                "fear": 0.1,
                "known_clue_ids": [clue_h.id],
                "version": watcher_pell.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_dockmaster = dockmaster.model_copy(
            update={
                "public_identity": "harbormaster, Docks authority",
                "hidden_objective": "Maintain control of what moves through unofficial channels.",
                "current_objective": "Keep port operations running without civic interference.",
                "trust_in_player": 0.15,
                "suspicion": 0.45,
                "fear": 0.1,
                "version": dockmaster.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_dock_hauler = dock_hauler.model_copy(
            update={
                "public_identity": "cargo hauler",
                "hidden_objective": "Avoid being connected to any unofficial cargo movements.",
                "current_objective": "Get through the day without drawing attention.",
                "trust_in_player": 0.3,
                "suspicion": 0.5,
                "fear": 0.35,
                "version": dock_hauler.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_records_broker = records_broker.model_copy(
            update={
                "public_identity": "commercial records clerk",
                "hidden_objective": "Leverage information asymmetry for personal gain.",
                "current_objective": "Identify what information the player is looking for and its value.",
                "trust_in_player": 0.2,
                "suspicion": 0.3,
                "fear": 0.05,
                "version": records_broker.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_guild_steward = guild_steward.model_copy(
            update={
                "public_identity": "trade guild compliance steward",
                "hidden_objective": "Protect guild interests from outside scrutiny.",
                "current_objective": "Enforce standard commercial procedures. Deflect irregular inquiries.",
                "trust_in_player": 0.1,
                "suspicion": 0.4,
                "fear": 0.1,
                "version": guild_steward.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_salvage_worker = salvage_worker.model_copy(
            update={
                "public_identity": "salvage worker, Salt Barrens",
                "hidden_objective": "Keep the graveyard and what it holds to himself.",
                "current_objective": "Work the yard. Stay out of trouble from both directions.",
                "trust_in_player": 0.35,
                "suspicion": 0.6,
                "fear": 0.5,
                "version": salvage_worker.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_route_warden = route_warden.model_copy(
            update={
                "public_identity": "maintenance route warden, Underways",
                "hidden_objective": (
                    "Protect the route network from outside interests — both faction and civic. "
                    "The Underways belongs to people who work it, not to people who permit it."
                ),
                "current_objective": (
                    "Maintain the junction. Know who is coming through and why. "
                    "Decide whether newcomers are useful or dangerous."
                ),
                "trust_in_player": 0.0,
                "suspicion": 0.7,
                "fear": 0.2,
                "version": route_warden.version + 1,
                "updated_at": TURN_ZERO,
            }
        )

        missing_clerk_case = self.store.load_object("CaseState", "case_missing_clerk")
        updated_missing_clerk_case = (
            missing_clerk_case.model_copy(
                update={
                    "hook_npc_id": updated_shrine_keeper.id,
                    "discovery_hook": (
                        "Ila Venn lowers her voice and admits that the archive lantern trouble "
                        "is tied to a missing registry clerk named Tovin Vale. She needs someone "
                        "outside the archive office to follow it before the record closes over him."
                    ),
                    "updated_at": TURN_ZERO,
                }
            )
            if isinstance(missing_clerk_case, CaseState)
            else None
        )

        self.store.save_objects_atomically(
            [
                updated_old_quarter,
                updated_lantern_ward,
                updated_shrine_keeper,
                updated_archive_clerk,
                updated_brin_hesse,
                updated_tovin_vale,
                shrine_lane,
                archive_steps,
                ledger_room,
                maintenance_route,
                service_passage,
                subarchive_chamber,
                lantern_square,
                clue_a,
                clue_b,
                clue_c,
                clue_d,
                clue_e,
                clue_f,
                clue_g,
                clue_h,
                clue_i,
                updated_sister_calis,
                updated_watcher_pell,
                regulation_office,
                ceremonial_walk,
                shrine_liaison_hall,
                civic_watch_desk,
                # New districts
                updated_the_docks,
                updated_market_spires,
                updated_salt_barrens,
                pier_landing,
                harbormaster_office,
                cargo_holding,
                dock_workers_passage,
                trade_floor,
                records_office,
                guild_hall,
                back_counter,
                abandoned_works,
                salvage_yard,
                lantern_graveyard,
                updated_dockmaster,
                updated_dock_hauler,
                updated_records_broker,
                updated_guild_steward,
                updated_salvage_worker,
                # Underways
                updated_underways,
                junction_hall,
                conduit_run,
                alteration_chamber,
                updated_route_warden,
                *([updated_missing_clerk_case] if updated_missing_clerk_case is not None else []),
            ]
        )

    def _introduce_case(self, case_id: str, *, updated_at: str | None = None) -> None:
        """Mark a case as known to the player so it appears in the sidebar."""
        pos = self._load_position()
        if pos is None or case_id in pos.known_case_ids:
            return
        self.store.save_object(
            pos.model_copy(
                update={
                    "known_case_ids": [*pos.known_case_ids, case_id],
                    "updated_at": updated_at or pos.updated_at,
                }
            )
        )

    def _acquire_clues(self, clue_ids: list[str], *, updated_at: str | None = None) -> None:
        """Merge clue_ids into the player's ActiveWorkingSet without duplicates."""
        if not clue_ids:
            return
        pos = self._load_position()
        if pos is None:
            return
        existing = set(pos.clue_ids)
        new_ids = [cid for cid in clue_ids if cid not in existing]
        if new_ids:
            self.store.save_object(
                pos.model_copy(
                    update={
                        "clue_ids": [*pos.clue_ids, *new_ids],
                        "updated_at": updated_at or pos.updated_at,
                    }
                )
            )

    def _load_position(self) -> ActiveWorkingSet | None:
        obj = self.store.load_object("ActiveWorkingSet", _AWS_ID)
        return obj if isinstance(obj, ActiveWorkingSet) else None

    def _save_position(self, *, updated_at: str | None = None, **updates: object) -> None:
        log.debug("_save_position %r", updates)
        city = self._require_city()
        pos = self._load_position()
        if pos is None:
            pos = ActiveWorkingSet(
                id=_AWS_ID,
                created_at=TURN_ZERO,
                updated_at=updated_at or turn_label(city.time_index),
                city_id=city.id,
            )
        self.store.save_object(
            pos.model_copy(update={**updates, "updated_at": updated_at or pos.updated_at})
        )

    def _request(
        self,
        intent: str,
        *,
        target_id: str | None = None,
        input_text: str = "",
        updated_at: str,
    ) -> PlayerRequest:
        request_id = f"request_{intent.replace(' ', '_')}_{target_id or 'none'}"
        return PlayerRequest(
            id=request_id,
            created_at=updated_at,
            updated_at=updated_at,
            player_id="player_001",
            intent=intent,
            target_id=target_id,
            input_text=input_text,
        )

    def _city(self):
        cities = self.store.list_objects("CityState")
        return None if not cities else cities[0]

    def _require_city(self):
        city = self._city()
        if city is None:
            raise LookupError("No active game. Run start first.")
        return city

    def _resolve_district_id(self, raw: str) -> str:
        """Return the canonical district_id for raw, falling back to name/fuzzy match."""
        city = self._city()
        if city is None:
            return raw
        # Exact match first
        if self._district(raw) is not None:
            log.debug("_resolve_district_id %r → exact match", raw)
            return raw
        # Fuzzy: compare lowercased name tokens against the raw string
        raw_lower = raw.lower().replace("_", " ").replace("-", " ")
        best: str | None = None
        best_score = 0
        for did in city.district_ids:
            d = self._district(did)
            if d is None:
                continue
            name_lower = d.name.lower()
            # Count shared words
            raw_words = set(raw_lower.split())
            name_words = set(name_lower.split())
            score = len(raw_words & name_words)
            # Also check if raw is contained in the id or vice versa
            did_lower = did.lower().replace("_", " ")
            if raw_lower in did_lower or did_lower in raw_lower:
                score += 2
            if score > best_score:
                best_score = score
                best = did
        resolved = best if best is not None and best_score > 0 else raw
        log.debug("_resolve_district_id %r → %r (score=%d)", raw, resolved, best_score)
        return resolved

    def _district(self, district_id: str) -> DistrictState | None:
        district = self.store.load_object("DistrictState", district_id)
        return district if isinstance(district, DistrictState) else None

    def _npc(self, npc_id: str) -> NPCState | None:
        npc = self.store.load_object("NPCState", npc_id)
        return npc if isinstance(npc, NPCState) else None

    def _active_case(self, city) -> object:
        if not city.active_case_ids:
            return None
        for case_id in city.active_case_ids:
            case = self.store.load_object("CaseState", case_id)
            if isinstance(case, CaseState) and case.status != "latent":
                return case
        return None

    def _npc_clue(self, npc: NPCState) -> ClueState | None:
        """Return the first non-solid clue from this NPC's known_clue_ids, or the primary clue."""
        for clue_id in npc.known_clue_ids:
            clue = self.store.load_object("ClueState", clue_id)
            if isinstance(clue, ClueState) and clue.reliability != "solid":
                return clue
        return self._primary_clue()

    def _primary_clue(self) -> ClueState | None:
        clue = self.store.load_object("ClueState", "clue_missing_clerk_ledgers")
        return clue if isinstance(clue, ClueState) else None

    def _require_progress(self) -> PlayerProgressState:
        progress_items = self.store.list_objects("PlayerProgressState")
        if not progress_items:
            raise LookupError("No player progress found")
        progress = progress_items[0]
        if not isinstance(progress, PlayerProgressState):
            raise TypeError("Stored progress is not a PlayerProgressState")
        return progress

    def _display_case_title(self, title: str) -> str:
        return title if title.lower().startswith("the ") else f"The {title}"


def _is_case_active(store: SQLiteStore, case_id: str) -> bool:
    c = store.load_object("CaseState", case_id)
    return isinstance(c, CaseState) and c.status == "active"


def _has_pre_case_signal(case_relevance: list[str] | None) -> bool:
    if not case_relevance:
        return False
    return any(item.startswith("New lead:") for item in case_relevance)


def _clue_label(clue_id: str) -> str:
    if clue_id.startswith("clue_"):
        return clue_id[5:].replace("_", " ").title()
    return clue_id


def _clue_sort_key(clue: ClueState) -> tuple[int, str]:
    order = {
        "solid": 0,
        "credible": 1,
        "uncertain": 2,
        "unstable": 3,
        "distorted": 4,
        "contradicted": 5,
    }
    return (order.get(clue.reliability, 9), clue.id)


def _case_sort_key(case: CaseState) -> tuple[int, int, str]:
    pressure_order = {
        "urgent": 0,
        "rising": 1,
        "low": 2,
    }
    status_order = {
        "active": 0,
        "escalated": 1,
        "stalled": 2,
        "partially solved": 3,
        "solved": 4,
        "failed": 5,
    }
    return (
        pressure_order.get(case.pressure_level, 9),
        status_order.get(case.status, 9),
        case.id,
    )


def _apply_physical_discovery(
    clue: ClueState,
    *,
    location_id: str,
    updated_at: str,
) -> ClueState:
    """Physical clues found at the inspected location upgrade to at least credible."""
    if clue.source_type != "physical":
        return clue
    if clue.source_id != location_id:
        return clue
    if clue.reliability in _CREDIBLE_RELIABILITIES or clue.reliability == "contradicted":
        return clue
    return clue.model_copy(update={"reliability": "credible", "updated_at": updated_at})


def _missingness_level(pressure: float) -> str:
    if pressure >= 0.67:
        return "high"
    if pressure >= 0.33:
        return "medium"
    if pressure > 0:
        return "low"
    return "none"


_CASE_CLUE_IDS = [
    "clue_missing_clerk_ledgers",
    "clue_heat_scoring_on_bracket",
    "clue_outage_predates_disappearance",
    "clue_missing_maintenance_line",
    "clue_family_record_discrepancy",
    "clue_hidden_copy_sheet",
    "clue_witness_instability",
    "clue_official_closure_order",
    "clue_ritual_authorization",
]
_CREDIBLE_RELIABILITIES = {"credible", "solid"}
# (track, amount, reason)
_RESOLUTION_GAINS: dict[str, list[tuple[str, int, str]]] = {
    "mvp_vertical_slice": [
        ("reputation", 8, "Recovered the missing clerk and established the core truth of the case."),
        ("city_impact", 6, "A deliberate disappearance failed to hold."),
        ("lantern_understanding", 6, "Confirmed how lantern distortion shaped the evidence trail."),
        ("clue_mastery", 6, "Turned one confirmed lead into a workable resolution."),
    ],
    "clean_exposure": [
        ("reputation", 10, "Public exposure of lantern manipulation and records fraud."),
        ("city_impact", 12, "Truth entered civic memory; district accountability forced."),
        ("access", 5, "Credibility gained through documented proof."),
        ("clue_mastery", 6, "Evidence chain assembled and presented under pressure."),
    ],
    "quiet_rescue": [
        ("access", 6, "Hidden routes used; Tovin extracted without public exposure."),
        ("reputation", 4, "Trusted by local actors for discretion."),
        ("leverage", 5, "Proof preserved; political use remains possible later."),
        ("clue_mastery", 4, "Case resolved through careful evidence handling."),
    ],
    "political_bargain": [
        ("leverage", 12, "Silence or partial silence traded for access or restoration."),
        ("access", 4, "Institutional doors opened through negotiation."),
        ("clue_mastery", 3, "Contradictions converted into durable leverage."),
    ],
    "partial_failure": [
        ("lantern_understanding", 4, "Lantern distortion identified and partially contained."),
        ("clue_mastery", 4, "Evidence gathered, case mechanism understood."),
    ],
    "burial": [
        ("lantern_understanding", 2, "Partial observation before the case closed against truth."),
    ],
}


def _assess_resolution(
    store: SQLiteStore, progress: PlayerProgressState
) -> tuple[str, str, str, str]:
    """Determine the resolution path, case status, and summary strings."""
    clues = [
        obj
        for clue_id in _CASE_CLUE_IDS
        if isinstance(obj := store.load_object("ClueState", clue_id), ClueState)
    ]
    credible_clues = [c for c in clues if c.reliability in _CREDIBLE_RELIABILITIES]
    clue_f = next((c for c in clues if c.id == "clue_hidden_copy_sheet"), None)
    has_clue_f = clue_f is not None and clue_f.reliability in _CREDIBLE_RELIABILITIES
    access_tier = get_tier(progress.access.score)
    leverage_tier = get_tier(progress.leverage.score)
    primary_clue = store.load_object("ClueState", "clue_missing_clerk_ledgers")
    shrine_keeper = store.load_object("NPCState", "npc_shrine_keeper")

    if (
        isinstance(primary_clue, ClueState)
        and primary_clue.reliability == "solid"
        and isinstance(shrine_keeper, NPCState)
        and len(shrine_keeper.memory_log) >= 1
    ):
        return (
            "mvp_vertical_slice",
            "solved",
            (
                "The altered ledger line was confirmed and Ila Venn's account held together under scrutiny. "
                "That was enough to recover Tovin Vale and prove the disappearance was engineered, even if the "
                "full civic fallout remains smaller than it would be in a broader case."
            ),
            (
                "The Missing Clerk case closes in MVP form. Tovin survives, the immediate distortion is broken, "
                "and the city now carries a recoverable scar instead of a total erasure."
            ),
        )

    if has_clue_f and len(credible_clues) >= 2 and (access_tier >= 2 or leverage_tier >= 2):
        return (
            "clean_exposure",
            "solved",
            (
                "Tovin Vale's hidden copy sheet, combined with physical evidence of deliberate "
                "lantern alteration, was presented to unavoidable authority. The manipulation "
                "entered the record. The district had to respond."
            ),
            (
                "Archive credibility shaken. Shrine Lane tensions surface. "
                "Old Quarter remembers this differently going forward."
            ),
        )

    if has_clue_f and len(credible_clues) >= 1:
        return (
            "quiet_rescue",
            "solved",
            (
                "Tovin Vale was located and extracted through the hidden route. "
                "Enough proof was preserved to prevent his disappearance from becoming permanent, "
                "but the full institutional truth was not forced into the public record."
            ),
            (
                "Tovin survives, off the books. Archive formally stable. "
                "Shrine keeper trust gains. The system that hid him remains."
            ),
        )

    if leverage_tier >= 2 and len(credible_clues) >= 1:
        return (
            "political_bargain",
            "solved",
            (
                "Evidence of the missing maintenance line and record discrepancies was used "
                "as leverage rather than public proof. An arrangement was reached. "
                "The case closes without scandal."
            ),
            (
                "Case closed quietly. One official remains compromised. "
                "Future cases may reference this silence."
            ),
        )

    if len(credible_clues) >= 1:
        return (
            "partial_failure",
            "partially solved",
            (
                "The lantern distortion was identified and partly stabilized, "
                "but the case closed without recovering Tovin Vale or proving full institutional guilt."
            ),
            (
                "District stops worsening. Records can be corrected later. "
                "Tovin's fate remains unresolved."
            ),
        )

    return (
        "burial",
        "failed",
        (
            "The investigation produced insufficient evidence before the case was forced to close. "
            "The official account hardened around the false version."
        ),
        (
            "Official records settle. District superficially calmer. "
            "Truth buried. Missingness pressure increases for future cases."
        ),
    )


def _assess_generated_resolution(
    case: CaseState, store: SQLiteStore
) -> tuple[str, str, str]:
    """Evaluate a generated case's stored resolution_conditions against current clue states."""
    if not case.resolution_conditions:
        return (
            "failed",
            "Insufficient evidence to resolve the case.",
            "The case closed without resolution.",
        )
    paths = sorted(case.resolution_conditions, key=lambda p: p.get("priority", 99))
    for path in paths:
        required_ids = path.get("required_clue_ids", [])
        required_count = int(path.get("required_credible_count", 0))
        credible_count = sum(
            1
            for clue_id in required_ids
            if isinstance(clue := store.load_object("ClueState", clue_id), ClueState)
            and clue.reliability in _CREDIBLE_RELIABILITIES
        )
        if credible_count >= required_count:
            return (
                str(path.get("outcome_status", "failed")),
                str(path.get("summary_text", "Case resolved.")),
                str(path.get("fallout_text", "")),
            )
    last = paths[-1]
    return (
        str(last.get("outcome_status", "failed")),
        str(last.get("summary_text", "Case closed without resolution.")),
        str(last.get("fallout_text", "")),
    )


def _gains_for_outcome(outcome_status: str) -> list[tuple[str, int, str]]:
    if outcome_status == "solved":
        return [
            ("reputation", 8, "Successfully resolved a generated investigation case."),
            ("city_impact", 10, "Case closure shaped the city's ongoing tensions."),
            ("clue_mastery", 5, "Evidence chain assembled and resolved."),
        ]
    if outcome_status == "partially solved":
        return [
            ("lantern_understanding", 4, "Partial resolution illuminated city dynamics."),
            ("clue_mastery", 4, "Evidence gathered; incomplete resolution."),
        ]
    return [
        ("lantern_understanding", 2, "Partial observation before case closed against truth."),
    ]


def _case_runtime_mode(case: CaseState) -> str:
    """Classify a case as the authored MVP baseline or the broader evolved runtime.

    This keeps the vertical-slice Missing Clerk path explicit in code instead of
    relying on an inline case-id special case inside command handling.
    """
    if case.id in _MVP_BASELINE_CASE_IDS:
        return "mvp_baseline"
    return "evolved_runtime"


def _tighten_district_access(current_access_level: str) -> str:
    if current_access_level in {"restricted", "controlled", "sealed"}:
        return current_access_level
    if current_access_level == "watched":
        return "restricted"
    if current_access_level in {"informal", "commercial", "open", "unknown"}:
        return "watched"
    return "watched"


def _surveil_district_access(current_access_level: str) -> str:
    if current_access_level in {"controlled", "sealed"}:
        return current_access_level
    if current_access_level == "restricted":
        return "controlled"
    if current_access_level == "watched":
        return "restricted"
    return "watched"


def _prioritized_faction_updates(notices: list[str], *, limit: int = 6) -> list[str]:
    def _priority(notice: str) -> tuple[int, int]:
        if "leaning on" in notice or "tightening pressure around" in notice:
            return (0, 0)
        if "isolating witnesses" in notice or "covering its tracks" in notice:
            return (0, 1)
        if "constricting access" in notice or "active faction pressure" in notice:
            return (1, 0)
        if "watching movement through" in notice:
            return (1, 1)
        if "now " in notice and "toward you" in notice:
            return (2, 0)
        if "moving around" in notice:
            return (3, 0)
        if "tightening its posture" in notice:
            return (4, 0)
        return (5, 0)

    ranked = sorted(enumerate(notices), key=lambda item: (_priority(item[1]), item[0]))
    return [notice for _, notice in ranked[:limit]]


def _load_default_seed() -> dict[str, object]:
    """Load the default offline seed from the bundled JSON file."""
    seed_path = Path(__file__).parent / "data" / "default_seed.json"
    return json.loads(seed_path.read_text(encoding="utf-8"))  # type: ignore[return-value]


def _default_seed_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "city_identity": {
            "city_name": "Lantern City",
            "dominant_mood": ["noir", "wet", "uncertain"],
            "weather_pattern": ["persistent rain", "coastal fog"],
            "architectural_style": ["old stone", "brass fixtures"],
            "economic_character": ["port trade", "recordkeeping"],
            "social_texture": ["guarded", "rumor-driven"],
            "ritual_texture": ["formal lantern ceremonies", "hidden shrine practice"],
            "baseline_noise_level": "medium",
        },
        "district_configuration": {
            "district_count": 6,
            "districts": [
                {
                    "id": "district_old_quarter",
                    "name": "Old Quarter",
                    "role": "memory/archive district",
                    "stability_baseline": 0.47,
                    "lantern_state": "dim",
                    "access_pattern": "restricted",
                    "hidden_location_density": "medium",
                    "social_rule": "speak carefully and never accuse without support",
                    "investigation_pressure": "contradiction",
                    "case_pattern_biases": ["records_tampering", "hidden_routes", "institutional_denial"],
                },
                {
                    "id": "district_lantern_ward",
                    "name": "Lantern Ward",
                    "role": "administrative lantern district",
                    "stability_baseline": 0.71,
                    "lantern_state": "bright",
                    "access_pattern": "controlled",
                    "hidden_location_density": "low",
                    "social_rule": "use proper channels and maintain composure",
                    "investigation_pressure": "legitimacy",
                    "case_pattern_biases": ["procedural_denial", "political_bargains", "official_reframing"],
                },
                {
                    "id": "district_the_docks",
                    "name": "The Docks",
                    "role": "transient port district",
                    "stability_baseline": 0.38,
                    "lantern_state": "flickering",
                    "access_pattern": "informal",
                    "hidden_location_density": "medium",
                    "social_rule": "pay attention to who owes whom before asking questions",
                    "investigation_pressure": "rumor_velocity",
                    "case_pattern_biases": ["smuggling", "displaced_witnesses", "shifting_testimony"],
                },
                {
                    "id": "district_market_spires",
                    "name": "Market Spires",
                    "role": "commercial trade district",
                    "stability_baseline": 0.62,
                    "lantern_state": "bright",
                    "access_pattern": "commercial",
                    "hidden_location_density": "low",
                    "social_rule": "status and transaction shape every conversation",
                    "investigation_pressure": "competitive_secrecy",
                    "case_pattern_biases": ["commercial_fraud", "records_brokers", "selective_access"],
                },
                {
                    "id": "district_salt_barrens",
                    "name": "Salt Barrens",
                    "role": "abandoned industrial outer district",
                    "stability_baseline": 0.18,
                    "lantern_state": "extinguished",
                    "access_pattern": "uncontrolled",
                    "hidden_location_density": "high",
                    "social_rule": "survival outranks procedure",
                    "investigation_pressure": "physical_hazard",
                    "case_pattern_biases": ["buried_evidence", "salvage_conflict", "memory_gaps"],
                },
                {
                    "id": "district_underways",
                    "name": "The Underways",
                    "role": "buried maintenance infrastructure district",
                    "stability_baseline": 0.25,
                    "lantern_state": "altered",
                    "access_pattern": "restricted",
                    "hidden_location_density": "high",
                    "social_rule": "everyone knows more than they say about the routes below",
                    "investigation_pressure": "route_instability",
                    "case_pattern_biases": ["access_distortion", "maintenance_coverups", "selective_missingness"],
                },
            ],
        },
        "faction_configuration": {
            "faction_count": 2,
            "factions": [
                {
                    "id": "faction_memory_keepers",
                    "name": "Memory Keepers",
                    "role": "memory stewardship",
                    "public_goal": "preserve continuity",
                    "hidden_goal": "control what the city remembers",
                    "influence_by_district": {
                        "district_old_quarter": 0.78,
                        "district_lantern_ward": 0.22,
                        "district_the_docks": 0.20,
                        "district_market_spires": 0.30,
                        "district_salt_barrens": 0.08,
                        "district_underways": 0.45,
                    },
                    "attitude_toward_player": "wary",
                    "methods": ["access control", "procedural delay", "controlled correction"],
                    "preferred_leverage": ["records", "certification", "legitimacy"],
                },
                {
                    "id": "faction_council_lights",
                    "name": "Council of Lights",
                    "role": "civic lantern administration",
                    "public_goal": "maintain public order",
                    "hidden_goal": "monopolize lantern legitimacy",
                    "influence_by_district": {
                        "district_old_quarter": 0.18,
                        "district_lantern_ward": 0.81,
                        "district_the_docks": 0.45,
                        "district_market_spires": 0.55,
                        "district_salt_barrens": 0.12,
                        "district_underways": 0.35,
                    },
                    "attitude_toward_player": "guarded",
                    "methods": ["official review", "public reassurance", "incident classification"],
                    "preferred_leverage": ["compliance", "public confidence", "access permits"],
                },
            ],
            "tension_map": {"faction_memory_keepers|faction_council_lights": 0.58},
        },
        "lantern_configuration": {
            "lantern_system_style": "civic grid with ritual overlays",
            "lantern_ownership_structure": "mixed control",
            "lantern_maintenance_structure": "shrine technicians and civic engineers",
            "lantern_condition_distribution": {
                "bright": 0.4,
                "dim": 0.35,
                "flickering": 0.15,
                "extinguished": 0.05,
                "altered": 0.05,
            },
            "lantern_reach_profile": "district-wide with street-level exceptions",
            "lantern_social_effect_profile": ["legitimacy", "restricted movement"],
            "lantern_memory_effect_profile": ["clearer testimony", "contradictory accounts"],
            "lantern_tampering_probability": 0.22,
            "altered_target_domain_weights": {
                "physical": 0.1,
                "records": 0.35,
                "testimony": 0.3,
                "composite": 0.15,
                "access": 0.1,
            },
        },
        "missingness_configuration": {
            "missingness_pressure": 0.42,
            "missingness_scope": "records first",
            "missingness_visibility": "known-but-denied",
            "missingness_style": "edited records and contradictory witness accounts",
            "missingness_targets": ["families", "archives"],
            "missingness_risk_level": "medium",
            "propagation_style": "person_to_record_to_event",
        },
        "case_configuration": {
            "starting_case_count": 1,
            "cases": [
                {
                    "id": "case_missing_clerk",
                    "type": "missing person",
                    "intensity": "medium",
                    "scope": "single district",
                    "involved_district_ids": ["district_old_quarter", "district_lantern_ward"],
                    "involved_faction_ids": ["faction_memory_keepers"],
                    "key_npc_ids": ["npc_shrine_keeper", "npc_archive_clerk", "npc_brin_hesse", "npc_tovin_vale"],
                    "failure_modes": ["evidence destroyed", "Missingness escalates"],
                }
            ],
        },
        "npc_configuration": {
            "tracked_npc_count": 12,
            "npcs": [
                {
                    "id": "npc_shrine_keeper",
                    "name": "Ila Venn",
                    "role_category": "informant",
                    "district_id": "district_old_quarter",
                    "location_id": "location_shrine_lane",
                    "memory_depth": "medium",
                    "relationship_density": "medium",
                    "secrecy_level": "high",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "immediate",
                },
                {
                    "id": "npc_archive_clerk",
                    "name": "Sered Marr",
                    "role_category": "gatekeeper",
                    "district_id": "district_old_quarter",
                    "location_id": "location_archive_steps",
                    "memory_depth": "high",
                    "relationship_density": "medium",
                    "secrecy_level": "high",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "immediate",
                },
                {
                    "id": "npc_brin_hesse",
                    "name": "Brin Hesse",
                    "role_category": "informant",
                    "district_id": "district_old_quarter",
                    "location_id": "location_maintenance_route",
                    "memory_depth": "low",
                    "relationship_density": "low",
                    "secrecy_level": "medium",
                    "mobility_pattern": "route-bound",
                    "relevance_level": "secondary",
                },
                {
                    "id": "npc_tovin_vale",
                    "name": "Tovin Vale",
                    "role_category": "informant",
                    "district_id": "district_old_quarter",
                    "location_id": "location_subarchive_chamber",
                    "memory_depth": "high",
                    "relationship_density": "low",
                    "secrecy_level": "extreme",
                    "mobility_pattern": "stationary",
                    "relevance_level": "immediate",
                },
                {
                    "id": "npc_sister_calis",
                    "name": "Sister Calis",
                    "role_category": "authority",
                    "district_id": "district_lantern_ward",
                    "location_id": "location_shrine_liaison_hall",
                    "memory_depth": "high",
                    "relationship_density": "medium",
                    "secrecy_level": "high",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "secondary",
                },
                {
                    "id": "npc_watcher_pell",
                    "name": "Watcher Pell",
                    "role_category": "gatekeeper",
                    "district_id": "district_lantern_ward",
                    "location_id": "location_civic_watch_desk",
                    "memory_depth": "medium",
                    "relationship_density": "low",
                    "secrecy_level": "medium",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "secondary",
                },
                {
                    "id": "npc_dockmaster",
                    "name": "Harrow Selt",
                    "role_category": "authority",
                    "district_id": "district_the_docks",
                    "location_id": "location_harbormaster_office",
                    "memory_depth": "medium",
                    "relationship_density": "medium",
                    "secrecy_level": "medium",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "secondary",
                },
                {
                    "id": "npc_dock_hauler",
                    "name": "Maren Osk",
                    "role_category": "informant",
                    "district_id": "district_the_docks",
                    "location_id": "location_cargo_holding",
                    "memory_depth": "low",
                    "relationship_density": "low",
                    "secrecy_level": "low",
                    "mobility_pattern": "route-bound",
                    "relevance_level": "background",
                },
                {
                    "id": "npc_records_broker",
                    "name": "Vel Dassen",
                    "role_category": "informant",
                    "district_id": "district_market_spires",
                    "location_id": "location_records_office",
                    "memory_depth": "high",
                    "relationship_density": "medium",
                    "secrecy_level": "medium",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "secondary",
                },
                {
                    "id": "npc_guild_steward",
                    "name": "Cor Falt",
                    "role_category": "gatekeeper",
                    "district_id": "district_market_spires",
                    "location_id": "location_guild_hall",
                    "memory_depth": "medium",
                    "relationship_density": "medium",
                    "secrecy_level": "medium",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "secondary",
                },
                {
                    "id": "npc_salvage_worker",
                    "name": "Persin Loke",
                    "role_category": "informant",
                    "district_id": "district_salt_barrens",
                    "location_id": "location_salvage_yard",
                    "memory_depth": "low",
                    "relationship_density": "low",
                    "secrecy_level": "low",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "background",
                },
                {
                    "id": "npc_route_warden",
                    "name": "Renn Dour",
                    "role_category": "informant",
                    "district_id": "district_underways",
                    "location_id": "location_junction_hall",
                    "memory_depth": "high",
                    "relationship_density": "low",
                    "secrecy_level": "high",
                    "mobility_pattern": "route-bound",
                    "relevance_level": "secondary",
                },
            ],
        },
        "progression_start_state": {
            "starting_lantern_understanding": 18,
            "starting_access": 10,
            "starting_reputation": 12,
            "starting_leverage": 5,
            "starting_city_impact": 2,
            "starting_clue_mastery": 20,
        },
        "tone_and_difficulty": {
            "story_density": "medium",
            "mystery_complexity": "medium",
            "social_resistance": "medium",
            "investigation_pace": "moderate",
            "consequence_severity": "medium",
            "revelation_delay": "medium",
            "narrative_strangeness": "medium",
            "replayability_profile": "district_pressure_and_faction_topology",
        },
    }


def _model_probe_messages() -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are validating whether a Lantern City-compatible model can produce one "
                "short, schema-compliant NPC response. Return valid JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                "Produce one bounded npc_response object for this scene.\n"
                "A cautious archive witness is asked who altered a maintenance ledger after dusk.\n"
                "The reply should be usable, concrete, and short. Avoid placeholders, ellipses, "
                "and transcript formatting. Include one useful follow-up suggestion."
            ),
        },
    ]


__all__ = ["LanternCityApp"]
