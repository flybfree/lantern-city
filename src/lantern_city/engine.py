from __future__ import annotations

from dataclasses import dataclass

from lantern_city.active_slice import ActiveSlice, RequestIntent
from lantern_city.models import ClueState, DistrictState, NPCState, PlayerRequest, RuntimeModel
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
) -> EngineOutcome:
    orchestrated = orchestrate_request(store, city_id=city_id, request=request)
    state_update_engine = StateUpdateEngine(store)

    if orchestrated.intent == "district_entry":
        response, changed_objects = _handle_district_entry(
            state_update_engine,
            orchestrated.active_slice,
            request,
        )
    elif orchestrated.intent == "talk_to_npc":
        response, changed_objects = _handle_npc_conversation(
            state_update_engine,
            orchestrated.active_slice,
            request,
        )
    elif orchestrated.intent == "inspect_location":
        response = _build_inspection_response(orchestrated.active_slice)
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
) -> tuple[ResponsePayload, list[str]]:
    city = active_slice.city
    district = _require_district(active_slice)
    case_title = None if active_slice.case is None else active_slice.case.title

    response = compose_response(
        narrative_text=(
            f"You enter {district.name}. The district feels {district.tone}, "
            f"and the lanterns are {district.lantern_condition}."
        ),
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
) -> tuple[ResponsePayload, list[str]]:
    npc = _require_npc(active_slice)
    clue = _first_clue(active_slice.clues)
    case_title = None if active_slice.case is None else active_slice.case.title
    public_identity = f", {npc.public_identity}" if npc.public_identity else ""
    quoted_input = request.input_text or "Ask a careful question."

    response = compose_response(
        narrative_text=(
            f'You ask {npc.name}{public_identity}, "{quoted_input}" '
            "They answer carefully and stay close to what is already known."
        ),
        state_changes=[f"Recorded a new conversation beat with {npc.name}."] if npc.name else [],
        learned=[] if clue is None else [clue.clue_text],
        now_available=_conversation_now_available(active_slice, npc),
        next_actions=_conversation_next_actions(case_title),
    )

    updated_npc = npc.model_copy(
        update={
            "memory_log": [
                *npc.memory_log,
                {
                    "request_id": request.id,
                    "intent": "talk_to_npc",
                    "input_text": request.input_text,
                },
            ],
            "version": npc.version + 1,
            "updated_at": request.updated_at,
        }
    )
    changed_objects = state_update_engine.apply_updates(updated_npc)
    return response, changed_objects


def _build_inspection_response(active_slice: ActiveSlice) -> ResponsePayload:
    location_name = "the area"
    if active_slice.location is not None:
        location_name = active_slice.location.name
    clue = _first_clue(active_slice.clues)
    learned = [] if clue is None else [clue.clue_text]
    return compose_response(
        narrative_text=f"You inspect {location_name} for anything that stands out.",
        learned=learned,
        now_available=["Ask about what you found"],
        next_actions=["Inspect a narrower detail", "Review known clues"],
    )


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
