from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from lantern_city.active_slice import ActiveSlice, build_active_slice
from lantern_city.models import PlayerRequest
from lantern_city.store import SQLiteStore

RequestIntent = Literal[
    "district_entry",
    "talk_to_npc",
    "inspect_location",
    "case_progression",
    "generic_action",
]

_DISTRICT_ENTRY_INTENTS = {"district entry", "district_entry", "enter district", "enter_district"}
_TALK_TO_NPC_INTENTS = {"talk to npc", "talk_to_npc", "talk", "speak", "conversation"}
_INSPECT_LOCATION_INTENTS = {
    "inspect location",
    "inspect_location",
    "inspect",
    "investigate",
    "observe",
}
_CASE_PROGRESSION_INTENTS = {
    "case progression",
    "case_progression",
    "advance case",
    "advance_case",
    "review case",
    "review_case",
    "case",
}


@dataclass(frozen=True, slots=True)
class OrchestratedRequest:
    request: PlayerRequest
    intent: RequestIntent
    active_slice: ActiveSlice


def classify_request_intent(request: PlayerRequest) -> RequestIntent:
    normalized_intent = _normalize_intent(request.intent)

    if normalized_intent in _DISTRICT_ENTRY_INTENTS:
        return "district_entry"
    if normalized_intent in _TALK_TO_NPC_INTENTS:
        return "talk_to_npc"
    if normalized_intent in _INSPECT_LOCATION_INTENTS:
        return "inspect_location"
    if normalized_intent in _CASE_PROGRESSION_INTENTS:
        return "case_progression"
    return "generic_action"


def orchestrate_request(
    store: SQLiteStore,
    *,
    city_id: str,
    request: PlayerRequest,
) -> OrchestratedRequest:
    intent = classify_request_intent(request)
    active_slice = build_active_slice(store, city_id=city_id, request=request, intent=intent)
    return OrchestratedRequest(request=request, intent=intent, active_slice=active_slice)


def _normalize_intent(raw_intent: str) -> str:
    return " ".join(raw_intent.strip().lower().replace("_", " ").split())


__all__ = ["OrchestratedRequest", "RequestIntent", "classify_request_intent", "orchestrate_request"]
