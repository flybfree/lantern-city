"""Bootstrap a generated case into the live world.

Takes a CaseGenerationResult (LLM output) and creates real CaseState,
NPCState, ClueState, and updated LocationState / DistrictState objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lantern_city.generation.case_generation import CaseGenerationResult
from lantern_city.models import (
    CaseState,
    CityState,
    ClueState,
    DistrictState,
    LocationState,
    NPCState,
    RelationshipSnapshot,
)
from lantern_city.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class CaseBootstrapResult:
    case: CaseState
    npcs: list[NPCState]
    clues: list[ClueState]
    updated_locations: list[LocationState]
    updated_districts: list[DistrictState]
    updated_city: CityState


def bootstrap_generated_case(
    result: CaseGenerationResult,
    *,
    store: SQLiteStore,
    city: CityState,
    case_index: int,
    updated_at: str,
) -> CaseBootstrapResult:
    """Deploy a CaseGenerationResult into the world as real stored objects."""
    case_id = f"case_gen_{case_index:03d}"

    # Load all district states and their locations
    districts: dict[str, DistrictState] = {}
    locations_by_district: dict[str, list[LocationState]] = {}

    for district_id in city.district_ids:
        obj = store.load_object("DistrictState", district_id)
        if isinstance(obj, DistrictState):
            districts[district_id] = obj
            locations_by_district[district_id] = []

    locations: dict[str, LocationState] = {}
    for district in districts.values():
        for loc_id in district.visible_locations + district.hidden_locations:
            obj = store.load_object("LocationState", loc_id)
            if isinstance(obj, LocationState):
                locations[loc_id] = obj
                locations_by_district.setdefault(obj.district_id, []).append(obj)

    # --- Create NPCs ---
    npcs: list[NPCState] = []
    npc_id_map: dict[int, str] = {}

    for i, spec in enumerate(result.npc_specs):
        npc_id = f"npc_{case_id}_{i:02d}"
        npc_id_map[i] = npc_id
        target_loc = _find_location(spec.district_id, spec.location_type_hint, locations_by_district)
        npcs.append(
            NPCState(
                id=npc_id,
                created_at=updated_at,
                updated_at=updated_at,
                name=spec.name,
                role_category=spec.role_category,
                district_id=spec.district_id,
                location_id=target_loc.id if target_loc else None,
                public_identity=spec.public_identity,
                hidden_objective=spec.hidden_objective,
                current_objective=spec.current_objective,
                trust_in_player=spec.trust_in_player,
                suspicion=spec.suspicion,
                fear=spec.fear,
                relationships={
                    "player": RelationshipSnapshot(
                        trust=spec.trust_in_player,
                        suspicion=spec.suspicion,
                        fear=spec.fear,
                        status="unknown",
                        last_updated_at=updated_at,
                    )
                },
                schedule_anchor=target_loc.id if target_loc else spec.district_id,
                offscreen_state="idle",
                relevance_rating=0.7,
            )
        )

    # --- Create clues ---
    clues: list[ClueState] = []
    clue_id_map: dict[int, str] = {}

    for i, spec in enumerate(result.clue_specs):
        clue_id = f"clue_{case_id}_{i:02d}"
        clue_id_map[i] = clue_id
        target_loc = _find_location(spec.district_id, spec.location_type_hint, locations_by_district)
        related_npc_ids: list[str] = []
        if spec.known_by_npc_index is not None and spec.known_by_npc_index in npc_id_map:
            related_npc_ids = [npc_id_map[spec.known_by_npc_index]]
        clues.append(
            ClueState(
                id=clue_id,
                created_at=updated_at,
                updated_at=updated_at,
                source_type=spec.source_type,
                source_id=target_loc.id if target_loc else spec.district_id,
                clue_text=spec.clue_text,
                reliability=spec.starting_reliability,
                related_npc_ids=related_npc_ids,
                related_case_ids=[case_id],
                related_district_ids=[spec.district_id],
            )
        )

    # Assign clue knowledge back onto NPCs
    final_npcs: list[NPCState] = []
    for i, npc in enumerate(npcs):
        known = [clue_id_map[j] for j, s in enumerate(result.clue_specs) if s.known_by_npc_index == i]
        final_npcs.append(npc.model_copy(update={"known_clue_ids": known}) if known else npc)

    # --- Resolve resolution paths: indices → real clue IDs ---
    resolution_conditions: list[dict] = []
    for path in sorted(result.resolution_paths, key=lambda p: p.priority):
        resolution_conditions.append({
            "path_id": path.path_id,
            "label": path.label,
            "outcome_status": path.outcome_status,
            "required_clue_ids": [clue_id_map[idx] for idx in path.required_clue_indices if idx in clue_id_map],
            "required_credible_count": path.required_credible_count,
            "summary_text": path.summary_text,
            "fallout_text": path.fallout_text,
            "priority": path.priority,
        })

    # --- Resolve hook NPC ---
    hook_npc_id = ""
    if result.hook_npc_index is not None and result.hook_npc_index in npc_id_map:
        hook_npc_id = npc_id_map[result.hook_npc_index]
    elif npc_id_map:
        hook_npc_id = npc_id_map[0]  # Default to first NPC if not specified

    # --- Create CaseState ---
    case = CaseState(
        id=case_id,
        created_at=updated_at,
        updated_at=updated_at,
        title=result.title,
        case_type=result.case_type,
        status="latent",
        involved_district_ids=list(result.involved_district_ids),
        involved_npc_ids=[npc.id for npc in final_npcs],
        known_clue_ids=[clue.id for clue in clues],
        open_questions=[s.clue_text[:80] for s in result.clue_specs[:3]],
        objective_summary=result.objective_summary,
        discovery_hook=result.opening_hook,
        hook_npc_id=hook_npc_id,
        resolution_conditions=resolution_conditions,
    )

    # --- Update locations: attach clue_ids and known_npc_ids ---
    loc_clues: dict[str, list[str]] = {}
    for clue in clues:
        if clue.source_id in locations:
            loc_clues.setdefault(clue.source_id, []).append(clue.id)

    loc_npcs: dict[str, list[str]] = {}
    for npc in final_npcs:
        if npc.location_id and npc.location_id in locations:
            loc_npcs.setdefault(npc.location_id, []).append(npc.id)

    # Merge updates keyed by location id
    loc_updates: dict[str, dict] = {}
    for loc_id, cids in loc_clues.items():
        loc_updates.setdefault(loc_id, {})["clue_ids"] = [*locations[loc_id].clue_ids, *cids]
    for loc_id, nids in loc_npcs.items():
        base = loc_updates.get(loc_id, {})
        existing_npc_ids = base.get("known_npc_ids", list(locations[loc_id].known_npc_ids))
        loc_updates.setdefault(loc_id, {})["known_npc_ids"] = [*existing_npc_ids, *nids]

    updated_locations = [
        locations[loc_id].model_copy(update={**updates, "updated_at": updated_at})
        for loc_id, updates in loc_updates.items()
    ]

    # --- Update districts: attach relevant_npc_ids ---
    district_npcs: dict[str, list[str]] = {}
    for npc in final_npcs:
        if npc.district_id:
            district_npcs.setdefault(npc.district_id, []).append(npc.id)

    updated_districts = [
        districts[did].model_copy(
            update={
                "relevant_npc_ids": [*districts[did].relevant_npc_ids, *nids],
                "updated_at": updated_at,
            }
        )
        for did, nids in district_npcs.items()
        if did in districts
    ]

    # --- Update city ---
    updated_city = city.model_copy(
        update={
            "active_case_ids": [
                *city.active_case_ids,
                *([case_id] if case_id not in city.active_case_ids else []),
            ],
            "updated_at": updated_at,
        }
    )

    return CaseBootstrapResult(
        case=case,
        npcs=final_npcs,
        clues=clues,
        updated_locations=updated_locations,
        updated_districts=updated_districts,
        updated_city=updated_city,
    )


def _find_location(
    district_id: str,
    location_type_hint: str,
    locations_by_district: dict[str, list[LocationState]],
) -> LocationState | None:
    candidates = locations_by_district.get(district_id, [])
    if not candidates:
        return None
    hint = location_type_hint.lower()
    best: LocationState | None = None
    best_score = -1
    for loc in candidates:
        loc_type = loc.location_type.lower()
        if loc_type == hint:
            score = 3
        elif hint in loc_type or loc_type in hint:
            score = 2
        elif any(word in loc_type for word in hint.split()):
            score = 1
        else:
            score = 0
        if score > best_score:
            best_score = score
            best = loc
    return best


__all__ = ["CaseBootstrapResult", "bootstrap_generated_case"]
