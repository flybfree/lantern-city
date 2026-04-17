from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from lantern_city.active_slice import ActiveSlice, RequestIntent
from lantern_city.generation.writing_guardrails import (
    COMMON_AVOID_RULES,
    DISTRICT_PROSE_RULES,
    TONE_SYSTEM_BLOCK,
)
from lantern_city.generation.location_inspection import (
    LocationInspectionError,
    LocationInspectionGenerator,
    LocationInspectionRequest,
)
from lantern_city.generation.npc_response import (
    NPCResponseGenerationError,
    NPCResponseGenerationRequest,
    NPCResponseGenerator,
)
from lantern_city.llm_client import OpenAICompatibleConfig, OpenAICompatibleLLMClient
from lantern_city.models import ClueState, DistrictState, NPCState, PlayerProgressState, PlayerRequest, RuntimeModel
from lantern_city.orchestrator import orchestrate_request
from lantern_city.response import ResponsePayload, compose_response
from lantern_city.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class EngineOutcome:
    intent: RequestIntent
    active_slice: ActiveSlice
    response: ResponsePayload
    changed_objects: list[str]


@dataclass(slots=True)
class StateUpdateEngine:
    store: SQLiteStore

    def apply_updates(self, *objects: RuntimeModel) -> list[str]:
        if not objects:
            return []
        self.store.save_objects_atomically(objects)
        return [f"{obj.type}:{obj.id}" for obj in objects]


def handle_player_request(
    store: SQLiteStore,
    *,
    city_id: str,
    request: PlayerRequest,
    llm_config: OpenAICompatibleConfig | None = None,
    progress: PlayerProgressState | None = None,
) -> EngineOutcome:
    orchestrated = orchestrate_request(store, city_id=city_id, request=request)
    state_update_engine = StateUpdateEngine(store)

    if orchestrated.intent == "district_entry":
        response, changed_objects = _handle_district_entry(
            state_update_engine,
            orchestrated.active_slice,
            request,
            llm_config=llm_config,
        )
    elif orchestrated.intent == "talk_to_npc":
        response, changed_objects = _handle_npc_conversation(
            state_update_engine,
            orchestrated.active_slice,
            request,
            llm_config=llm_config,
            progress=progress,
        )
    elif orchestrated.intent == "inspect_location":
        response = _build_inspection_response(
            orchestrated.active_slice, request, llm_config=llm_config, progress=progress
        )
        changed_objects = []
    elif orchestrated.intent == "case_progression":
        response = _build_case_response(orchestrated.active_slice)
        changed_objects = []
    else:
        response = compose_response(
            narrative_text="You pause and take stock of the scene.",
            next_actions=["Review what stands out", "Choose a more specific action"],
        )
        changed_objects = []

    return EngineOutcome(
        intent=orchestrated.intent,
        active_slice=orchestrated.active_slice,
        response=response,
        changed_objects=changed_objects,
    )


def _handle_district_entry(
    state_update_engine: StateUpdateEngine,
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None = None,
) -> tuple[ResponsePayload, list[str]]:
    city = active_slice.city
    district = _require_district(active_slice)
    case_title = None if active_slice.case is None else active_slice.case.title

    entry_prose = _generate_district_entry_prose(active_slice, llm_config=llm_config)
    narrative_text = entry_prose or (
        f"You enter {district.name}. The lanterns are {district.lantern_condition}."
    )

    response = compose_response(
        narrative_text=narrative_text,
        state_changes=[f"Presence increased in {district.name}."] if district.name else [],
        learned=[f"The district lanterns are running {district.lantern_condition}."],
        now_available=_district_now_available(district, active_slice.npcs),
        next_actions=_district_next_actions(district, case_title),
    )

    updated_city = city.model_copy(
        update={
            "player_presence_level": round(min(city.player_presence_level + 0.1, 1.0), 3),
            "version": city.version + 1,
            "updated_at": request.updated_at,
        }
    )
    changed_objects = state_update_engine.apply_updates(updated_city)
    return response, changed_objects


def _handle_npc_conversation(
    state_update_engine: StateUpdateEngine,
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None = None,
    progress: PlayerProgressState | None = None,
) -> tuple[ResponsePayload, list[str]]:
    npc = _require_npc(active_slice)
    clue = _first_clue(active_slice.clues)
    case_title = None if active_slice.case is None else active_slice.case.title

    npc_line = _generate_npc_dialogue(active_slice, request, llm_config=llm_config, progress=progress)
    if npc_line is None:
        public_identity = f", {npc.public_identity}" if npc.public_identity else ""
        quoted_input = request.input_text or "Ask a careful question."
        narrative_text = (
            f'You ask {npc.name}{public_identity}, "{quoted_input}" '
            "They answer carefully and stay close to what is already known."
        )
    else:
        narrative_text = npc_line

    response = compose_response(
        narrative_text=narrative_text,
        state_changes=[f"Recorded a new conversation beat with {npc.name}."] if npc.name else [],
        learned=[] if clue is None else [clue.clue_text],
        now_available=_conversation_now_available(active_slice, npc),
        next_actions=_conversation_next_actions(case_title),
    )

    memory_entry: dict[str, str] = {
        "request_id": request.id,
        "intent": "talk_to_npc",
        "input_text": request.input_text,
    }
    if npc_line is not None:
        memory_entry["npc_response"] = npc_line

    updated_npc = npc.model_copy(
        update={
            "memory_log": [
                *npc.memory_log,
                memory_entry,
            ],
            "version": npc.version + 1,
            "updated_at": request.updated_at,
        }
    )
    changed_objects = state_update_engine.apply_updates(updated_npc)
    return response, changed_objects


def _build_inspection_response(
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None = None,
    progress: PlayerProgressState | None = None,
) -> ResponsePayload:
    location_name = "the area"
    if active_slice.location is not None:
        location_name = active_slice.location.name

    prose = _generate_inspection_prose(active_slice, request, llm_config=llm_config, progress=progress)
    if prose is not None:
        narrative_text, learned, next_actions = prose
    else:
        clue = _first_clue(active_slice.clues)
        narrative_text = f"You inspect {location_name} for anything that stands out."
        learned = [] if clue is None else [clue.clue_text]
        next_actions = ["Inspect a narrower detail", "Review known clues"]

    return compose_response(
        narrative_text=narrative_text,
        learned=learned,
        now_available=["Ask about what you found"],
        next_actions=next_actions,
    )


def _generate_inspection_prose(
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None,
    progress: PlayerProgressState | None = None,
) -> tuple[str, list[str], list[str]] | None:
    if llm_config is None:
        return None
    try:
        llm_client = OpenAICompatibleLLMClient(llm_config)
        gen_request = LocationInspectionRequest(
            request_id=request.id,
            active_slice=active_slice,
            player_request=request,
            progress=progress,
        )
        result = LocationInspectionGenerator(llm_client).generate(gen_request)
        llm_client.close()

        def _ensure_period(s: str) -> str:
            s = s.strip()
            return s if s.endswith((".", "!", "?")) else s + "."

        parts = [_ensure_period(result.scene_text)]
        if result.lantern_effect:
            parts.append(_ensure_period(result.lantern_effect))
        if result.clue_connection:
            parts.append(_ensure_period(result.clue_connection))
        narrative_text = " ".join(parts)

        learned = result.notable_details
        next_actions = ["Ask an NPC about what you found", "Inspect a narrower detail"]
        return narrative_text, learned, next_actions
    except (LocationInspectionError, Exception) as exc:
        print(f"[LLM] inspection generation failed: {exc}", file=sys.stderr)
        return None


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks and leading reasoning headers from model output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    lines = text.splitlines()
    prose_lines = []
    skip = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^(thinking|reasoning|thought process|step \d)", stripped, re.IGNORECASE):
            skip = True
            continue
        if skip and re.match(r"^\d+\.", stripped):
            continue
        if skip and stripped and not re.match(r"^\d+\.", stripped):
            skip = False
        if not skip:
            prose_lines.append(line)
    return "\n".join(prose_lines).strip()


def _generate_district_entry_prose(
    active_slice: ActiveSlice,
    *,
    llm_config: OpenAICompatibleConfig | None,
) -> str | None:
    if llm_config is None or active_slice.district is None:
        return None
    try:
        district = active_slice.district
        city = active_slice.city
        case_title = None if active_slice.case is None else active_slice.case.title
        npc_names = [npc.name for npc in active_slice.npcs if npc.name]

        npc_hint = f" {npc_names[0]} can be found here." if npc_names else ""
        case_hint = f" An active case draws you here: {case_title}." if case_title else ""

        prompt = (
            f"Write 2-3 sentences of atmospheric entry prose for a player arriving in "
            f"{district.name}, a {district.tone} district. "
            f"The lanterns are {district.lantern_condition}. "
            f"Access is {district.current_access_level}."
            f"{case_hint}{npc_hint}\n\n"
            f"Rules:\n{DISTRICT_PROSE_RULES}\n{COMMON_AVOID_RULES}"
        )
        schema = {
            "type": "object",
            "properties": {"prose": {"type": "string"}},
            "required": ["prose"],
        }
        llm_client = OpenAICompatibleLLMClient(llm_config)
        result = llm_client.generate_json(
            messages=[
                {"role": "system", "content": f"You write terse atmospheric prose for a text RPG. Return valid JSON only. {TONE_SYSTEM_BLOCK}"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=1000,
            schema=schema,
        )
        llm_client.close()
        prose = (result.get("prose") or "").strip().strip('"')
        return prose if prose else None
    except Exception as exc:
        print(f"[LLM] district entry generation failed: {exc}", file=sys.stderr)
        return None


def _build_case_response(active_slice: ActiveSlice) -> ResponsePayload:
    if active_slice.case is None:
        return compose_response(
            narrative_text="You review your current leads, but no active case is focused here.",
            next_actions=["Choose a district lead", "Speak to a local contact"],
        )
    return compose_response(
        narrative_text=f"You review {active_slice.case.title}.",
        learned=list(active_slice.case.open_questions),
        now_available=["Follow a case lead"],
        next_actions=["Inspect related evidence", "Speak to an involved NPC"],
    )


def _generate_npc_dialogue(
    active_slice: ActiveSlice,
    request: PlayerRequest,
    *,
    llm_config: OpenAICompatibleConfig | None,
    progress: PlayerProgressState | None = None,
) -> str | None:
    if llm_config is None or not active_slice.npcs:
        return None
    try:
        llm_client = OpenAICompatibleLLMClient(llm_config)
        gen_request = NPCResponseGenerationRequest(
            request_id=request.id,
            active_slice=active_slice,
            player_request=request,
            npc_id=request.target_id,
            progress=progress,
        )
        result = NPCResponseGenerator(llm_client).generate(gen_request, max_tokens=2000)
        llm_client.close()
        return result.cacheable_text.npc_line
    except (NPCResponseGenerationError, Exception) as exc:
        print(f"[LLM] generation failed: {exc}", file=sys.stderr)
        return None


def _district_now_available(district: DistrictState, npcs: list[NPCState]) -> list[str]:
    available: list[str] = []
    if district.visible_locations:
        available.append(f"Travel to {_display_name(district.visible_locations[0])}")
    if npcs:
        available.append(f"Speak to {npcs[0].name}")
    return available


def _district_next_actions(district: DistrictState, case_title: str | None) -> list[str]:
    next_actions: list[str] = []
    if district.visible_locations:
        next_actions.append(f"Inspect {_display_name(district.visible_locations[0])}")
    if case_title is not None:
        next_actions.append(f"Review {case_title}")
    return next_actions


def _conversation_now_available(active_slice: ActiveSlice, npc: NPCState) -> list[str]:
    available: list[str] = []
    if active_slice.location is not None:
        available.append(f"Inspect {active_slice.location.name}")
    elif npc.location_id is not None:
        available.append(f"Inspect {_display_name(npc.location_id)}")
    available.append(f"Press {npc.name} for specifics")
    return available


def _conversation_next_actions(case_title: str | None) -> list[str]:
    next_actions = ["Ask a narrower question"]
    if case_title is not None:
        next_actions.append(f"Review {case_title}")
    return next_actions


def _require_district(active_slice: ActiveSlice) -> DistrictState:
    if active_slice.district is None:
        raise LookupError("District request requires an active district slice")
    return active_slice.district


def _require_npc(active_slice: ActiveSlice) -> NPCState:
    if not active_slice.npcs:
        raise LookupError("Conversation request requires an active NPC slice")
    return active_slice.npcs[0]


def _first_clue(clues: list[ClueState]) -> ClueState | None:
    if not clues:
        return None
    return clues[0]


def _display_name(identifier: str) -> str:
    if identifier.startswith(("location_", "district_", "case_", "npc_")):
        return identifier.split("_", 1)[1].replace("_", " ").title()
    return identifier


__all__ = ["EngineOutcome", "StateUpdateEngine", "handle_player_request"]
