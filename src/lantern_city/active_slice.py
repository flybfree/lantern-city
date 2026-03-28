from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

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


class MissingWorldObjectError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class ActiveSlice:
    working_set: ActiveWorkingSet
    district: DistrictState | None
    location: LocationState | None
    scene: SceneState | None
    npcs: list[NPCState]
    clues: list[ClueState]
    case: CaseState | None


def build_active_slice(
    store: SQLiteStore,
    *,
    city_id: str,
    request: PlayerRequest,
    intent: RequestIntent | None = None,
) -> ActiveSlice:
    resolved_intent = intent or _classify_request_intent(request)
    city = _load_required(store, "CityState", city_id, CityState)

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
            city_id=city.id,
            district=None,
            location=None,
            scene=None,
            npcs=[],
            clues=[],
            case=None,
        )

    scene_id = _reference_from_request(request, "scene_id")
    scene = _load_optional(store, "SceneState", scene_id, SceneState)

    npc_ids = _initial_npc_ids(resolved_intent, request, scene)
    npcs = _load_unique_required(store, "NPCState", npc_ids, NPCState)

    location_id = _resolve_location_id(request, scene, npcs)
    location = _load_optional(store, "LocationState", location_id, LocationState)

    district_id = _resolve_district_id(request, location, npcs)
    district = _load_optional(store, "DistrictState", district_id, DistrictState)

    if district is None and resolved_intent == "district_entry" and request.target_id is not None:
        district = _load_required(store, "DistrictState", request.target_id, DistrictState)

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

    case_id = _resolve_case_id(store, request, city, scene, district, npcs)
    case = _load_optional(store, "CaseState", case_id, CaseState)

    clue_ids = _resolve_clue_ids(scene, location, npcs, case)
    clues = _load_unique_required(store, "ClueState", clue_ids, ClueState)

    return _build_slice(
        city_id=city.id,
        district=district,
        location=location,
        scene=scene,
        npcs=npcs,
        clues=clues,
        case=case,
    )


def _build_slice(
    *,
    city_id: str,
    district: DistrictState | None,
    location: LocationState | None,
    scene: SceneState | None,
    npcs: list[NPCState],
    clues: list[ClueState],
    case: CaseState | None,
) -> ActiveSlice:
    npc_ids = [npc.id for npc in npcs]
    clue_ids = [clue.id for clue in clues]
    working_set = ActiveWorkingSet(
        id=f"active_working_set_{city_id}",
        created_at="turn_0",
        updated_at="turn_0",
        city_id=city_id,
        district_id=None if district is None else district.id,
        location_id=None if location is None else location.id,
        case_id=None if case is None else case.id,
        scene_id=None if scene is None else scene.id,
        npc_ids=npc_ids,
        clue_ids=clue_ids,
    )
    return ActiveSlice(
        working_set=working_set,
        district=district,
        location=location,
        scene=scene,
        npcs=npcs,
        clues=clues,
        case=case,
    )


def _initial_npc_ids(
    intent: RequestIntent,
    request: PlayerRequest,
    scene: SceneState | None,
) -> list[str]:
    npc_ids: list[str] = []
    if intent == "talk_to_npc" and request.target_id is not None:
        npc_ids.append(request.target_id)
    if scene is not None:
        npc_ids.extend(scene.participating_npc_ids)
    return _dedupe_preserve_order(npc_ids)


def _resolve_location_id(
    request: PlayerRequest,
    scene: SceneState | None,
    npcs: list[NPCState],
) -> str | None:
    if request.location_id is not None:
        return request.location_id
    target_id = request.target_id
    if target_id is not None and target_id.startswith("location_"):
        return target_id
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
) -> str | None:
    target_id = request.target_id
    if target_id is not None and target_id.startswith("district_"):
        return target_id
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
) -> str | None:
    explicit_case_id = _reference_from_request(request, "case_id")
    if explicit_case_id is not None:
        return explicit_case_id
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


def _classify_request_intent(request: PlayerRequest) -> RequestIntent:
    normalized_intent = " ".join(request.intent.strip().lower().replace("_", " ").split())
    if normalized_intent in {"district entry", "enter district"}:
        return "district_entry"
    if normalized_intent in {"talk to npc", "talk", "speak", "conversation"}:
        return "talk_to_npc"
    if normalized_intent in {"inspect location", "inspect", "investigate", "observe"}:
        return "inspect_location"
    if normalized_intent in {"case progression", "advance case", "review case", "case"}:
        return "case_progression"
    return "generic_action"


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


__all__ = ["ActiveSlice", "MissingWorldObjectError", "build_active_slice"]
