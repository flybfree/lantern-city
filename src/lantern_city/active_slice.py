from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, cast

from lantern_city.models import (
    ActiveWorkingSet,
    CaseState,
    CityState,
    ClueState,
    DistrictState,
    LocationState,
    NPCState,
    PlayerRequest,
    SceneState,
)
from lantern_city.store import SQLiteStore

RequestIntent = Literal[
    "district_entry",
    "talk_to_npc",
    "inspect_location",
    "case_progression",
    "generic_action",
]

_DISTRICT_ENTRY_INTENTS: Final[set[str]] = {
    "district entry",
    "district_entry",
    "enter district",
    "enter_district",
}
_TALK_TO_NPC_INTENTS: Final[set[str]] = {
    "talk to npc",
    "talk_to_npc",
    "talk",
    "speak",
    "conversation",
}
_INSPECT_LOCATION_INTENTS: Final[set[str]] = {
    "inspect location",
    "inspect_location",
    "inspect",
    "investigate",
    "observe",
}
_CASE_PROGRESSION_INTENTS: Final[set[str]] = {
    "case progression",
    "case_progression",
    "advance case",
    "advance_case",
    "review case",
    "review_case",
    "case",
}


class MissingWorldObjectError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class ActiveSlice:
    city: CityState
    working_set: ActiveWorkingSet
    district: DistrictState | None
    location: LocationState | None
    scene: SceneState | None
    npcs: list[NPCState]
    clues: list[ClueState]
    case: CaseState | None


TargetObjectType = Literal["district", "location", "npc", "case", "scene"]


@dataclass(frozen=True, slots=True)
class RequestTarget:
    target_type: TargetObjectType
    target_id: str


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


def build_active_slice(
    store: SQLiteStore,
    *,
    city_id: str,
    request: PlayerRequest,
    intent: RequestIntent | None = None,
) -> ActiveSlice:
    resolved_intent = intent or classify_request_intent(request)
    city = _load_required(store, "CityState", city_id, CityState)
    request_target = _resolve_request_target(request, resolved_intent)
    _raise_for_unresolved_explicit_target(request, request_target)

    if resolved_intent == "generic_action" and not any(
        [
            request.target_id,
            request.location_id,
            request.case_id,
            request.scene_id,
            request.context_refs,
        ]
    ):
        return _build_slice(
            request_id=request.id,
            city=city,
            district=None,
            location=None,
            scene=None,
            npcs=[],
            clues=[],
            case=None,
        )

    scene_id = _reference_from_request(request, "scene_id")
    scene = _load_optional(store, "SceneState", scene_id, SceneState)

    npc_ids = _initial_npc_ids(request_target, scene)
    npcs = _load_unique_required(store, "NPCState", npc_ids, NPCState)

    location_id = _resolve_location_id(request, scene, npcs, request_target)
    location = _load_optional(store, "LocationState", location_id, LocationState)

    district_id = _resolve_district_id(request, location, npcs, request_target)
    district = _load_optional(store, "DistrictState", district_id, DistrictState)

    if district is None and resolved_intent in {
        "district_entry",
        "talk_to_npc",
        "inspect_location",
    }:
        message = f"Unable to resolve district for request {request.id}"
        raise MissingWorldObjectError(message)

    if resolved_intent == "district_entry" and district is not None:
        npcs = _load_unique_required(store, "NPCState", district.relevant_npc_ids, NPCState)
    elif resolved_intent == "inspect_location" and location is not None:
        npcs = _load_unique_required(store, "NPCState", location.known_npc_ids, NPCState)

    case_id = _resolve_case_id(store, request, city, scene, district, npcs, request_target)
    case = _load_optional(store, "CaseState", case_id, CaseState)

    clue_ids = _resolve_clue_ids(scene, location, npcs, case)
    clues = _load_unique_required(store, "ClueState", clue_ids, ClueState)

    return _build_slice(
        request_id=request.id,
        city=city,
        district=district,
        location=location,
        scene=scene,
        npcs=npcs,
        clues=clues,
        case=case,
    )


def _build_slice(
    *,
    request_id: str,
    city: CityState,
    district: DistrictState | None,
    location: LocationState | None,
    scene: SceneState | None,
    npcs: list[NPCState],
    clues: list[ClueState],
    case: CaseState | None,
) -> ActiveSlice:
    npc_ids = [npc.id for npc in npcs]
    clue_ids = [clue.id for clue in clues]
    metadata_token = f"synthetic_active_slice_request_{request_id}"
    working_set = ActiveWorkingSet(
        id=f"synthetic_active_working_set_{city.id}_{request_id}",
        created_at=metadata_token,
        updated_at=metadata_token,
        city_id=city.id,
        district_id=None if district is None else district.id,
        location_id=None if location is None else location.id,
        case_id=None if case is None else case.id,
        scene_id=None if scene is None else scene.id,
        npc_ids=npc_ids,
        clue_ids=clue_ids,
    )
    return ActiveSlice(
        city=city,
        working_set=working_set,
        district=district,
        location=location,
        scene=scene,
        npcs=npcs,
        clues=clues,
        case=case,
    )


def _initial_npc_ids(
    request_target: RequestTarget | None,
    scene: SceneState | None,
) -> list[str]:
    npc_ids: list[str] = []
    if request_target is not None and request_target.target_type == "npc":
        npc_ids.append(request_target.target_id)
    if scene is not None:
        npc_ids.extend(scene.participating_npc_ids)
    return _dedupe_preserve_order(npc_ids)


def _resolve_location_id(
    request: PlayerRequest,
    scene: SceneState | None,
    npcs: list[NPCState],
    request_target: RequestTarget | None,
) -> str | None:
    if request.location_id is not None:
        return request.location_id
    if request_target is not None and request_target.target_type == "location":
        return request_target.target_id
    if scene is not None and scene.location_id is not None:
        return scene.location_id
    for npc in npcs:
        if npc.location_id is not None:
            return npc.location_id
    location_id = _reference_from_request(request, "location_id")
    return None if location_id is None else str(location_id)


def _resolve_district_id(
    request: PlayerRequest,
    location: LocationState | None,
    npcs: list[NPCState],
    request_target: RequestTarget | None,
) -> str | None:
    if request_target is not None and request_target.target_type == "district":
        return request_target.target_id
    district_id = _reference_from_request(request, "district_id")
    if district_id is not None:
        return district_id
    if location is not None:
        return location.district_id
    for npc in npcs:
        if npc.district_id is not None:
            return npc.district_id
    return None


def _resolve_case_id(
    store: SQLiteStore,
    request: PlayerRequest,
    city: CityState,
    scene: SceneState | None,
    district: DistrictState | None,
    npcs: list[NPCState],
    request_target: RequestTarget | None,
) -> str | None:
    explicit_case_id = _reference_from_request(request, "case_id")
    if explicit_case_id is not None:
        return explicit_case_id
    if request_target is not None and request_target.target_type == "case":
        return request_target.target_id
    if scene is not None and scene.case_id is not None:
        return scene.case_id

    relevant_case_ids: list[str] = []
    district_id = None if district is None else district.id
    npc_ids = {npc.id for npc in npcs}
    for case_id in city.active_case_ids:
        case = _load_optional(store, "CaseState", case_id, CaseState)
        if case is None:
            continue
        if district_id is not None and district_id in case.involved_district_ids:
            relevant_case_ids.append(case.id)
            continue
        if npc_ids.intersection(case.involved_npc_ids):
            relevant_case_ids.append(case.id)

    unique_case_ids = _dedupe_preserve_order(relevant_case_ids)
    if len(unique_case_ids) == 1:
        return unique_case_ids[0]
    return None


def _resolve_clue_ids(
    scene: SceneState | None,
    location: LocationState | None,
    npcs: list[NPCState],
    case: CaseState | None,
) -> list[str]:
    clue_ids: list[str] = []
    if scene is not None:
        clue_ids.extend(scene.scene_clue_ids)
    if location is not None:
        clue_ids.extend(location.clue_ids)
    for npc in npcs:
        clue_ids.extend(npc.known_clue_ids)
    if not clue_ids and case is not None:
        clue_ids.extend(case.known_clue_ids)
    return sorted(_dedupe_preserve_order(clue_ids))


def _reference_from_request(request: PlayerRequest, key: str) -> str | None:
    value = getattr(request, key, None)
    if value is not None:
        return value
    from_context = request.context_refs.get(key)
    if from_context is None:
        return None
    return str(from_context)


def _resolve_request_target(
    request: PlayerRequest,
    intent: RequestIntent,
) -> RequestTarget | None:
    if request.target_id is None:
        return None

    explicit_target_type = _request_target_type(request)
    if explicit_target_type is not None:
        return RequestTarget(target_type=explicit_target_type, target_id=request.target_id)

    intent_target_types: dict[RequestIntent, TargetObjectType] = {
        "district_entry": "district",
        "talk_to_npc": "npc",
        "inspect_location": "location",
        "case_progression": "case",
    }
    intent_target_type = intent_target_types.get(intent)
    if intent_target_type is not None:
        return RequestTarget(target_type=intent_target_type, target_id=request.target_id)

    for prefix, target_type in (
        ("district_", "district"),
        ("location_", "location"),
        ("npc_", "npc"),
        ("case_", "case"),
        ("scene_", "scene"),
    ):
        if request.target_id.startswith(prefix):
            return RequestTarget(target_type=target_type, target_id=request.target_id)
    return None


def _raise_for_unresolved_explicit_target(
    request: PlayerRequest,
    request_target: RequestTarget | None,
) -> None:
    if request.target_id is None or request_target is not None:
        return

    raw_target_type = request.context_refs.get("target_type")
    target_type_suffix = ""
    if raw_target_type is not None:
        target_type_suffix = f", target_type={raw_target_type!r}"
    raise ValueError(
        "Unable to resolve request target "
        f"for request {request.id}: target_id={request.target_id!r}{target_type_suffix}"
    )



def _request_target_type(request: PlayerRequest) -> TargetObjectType | None:
    raw_target_type = request.context_refs.get("target_type")
    if raw_target_type is None:
        return None

    normalized_target_type = str(raw_target_type).strip().lower().replace("-", "_")
    target_type_aliases: dict[str, TargetObjectType] = {
        "district": "district",
        "location": "location",
        "npc": "npc",
        "case": "case",
        "scene": "scene",
    }
    return target_type_aliases.get(normalized_target_type)


def _normalize_intent(raw_intent: str) -> str:
    return " ".join(raw_intent.strip().lower().replace("_", " ").split())


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _load_optional[T](
    store: SQLiteStore,
    object_type: str,
    object_id: str | None,
    model_type: type[T],
) -> T | None:
    if object_id is None:
        return None
    loaded = store.load_object(object_type, object_id)
    if loaded is None:
        raise MissingWorldObjectError(f"Missing required world object {object_type}:{object_id}")
    if not isinstance(loaded, model_type):
        raise TypeError(f"Expected {model_type.__name__} for {object_type}:{object_id}")
    return cast(T, loaded)


def _load_required[T](
    store: SQLiteStore,
    object_type: str,
    object_id: str,
    model_type: type[T],
) -> T:
    loaded = _load_optional(store, object_type, object_id, model_type)
    if loaded is None:
        raise MissingWorldObjectError(f"Missing required world object {object_type}:{object_id}")
    return loaded


def _load_unique_required[T](
    store: SQLiteStore,
    object_type: str,
    object_ids: list[str],
    model_type: type[T],
) -> list[T]:
    return [
        _load_required(store, object_type, object_id, model_type)
        for object_id in _dedupe_preserve_order(object_ids)
    ]


__all__ = [
    "ActiveSlice",
    "MissingWorldObjectError",
    "RequestIntent",
    "build_active_slice",
    "classify_request_intent",
]
