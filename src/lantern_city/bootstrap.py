from __future__ import annotations

import re
from dataclasses import dataclass

from lantern_city.models import (
    CaseState,
    CitySeed,
    CityState,
    DistrictState,
    FactionState,
    LanternState,
    NPCState,
    PlayerProgressState,
    RelationshipSnapshot,
    ScoreTier,
)
from lantern_city.progression import get_tier, get_tier_label
from lantern_city.seed_schema import CitySeedDocument
from lantern_city.store import SQLiteStore

TURN_ZERO = "turn_0"
RELEVANCE_RATINGS = {
    "background": 0.2,
    "low": 0.3,
    "medium": 0.5,
    "high": 0.7,
    "immediate": 0.9,
    "critical": 1.0,
}


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    city_seed_id: str
    city_id: str
    player_progress_id: str
    district_ids: list[str]
    faction_ids: list[str]
    lantern_ids: list[str]
    case_ids: list[str]
    npc_ids: list[str]


def bootstrap_city(seed: CitySeedDocument, store: SQLiteStore) -> BootstrapResult:
    city_slug = _slugify(seed.city_identity.city_name)
    city_seed_id = f"cityseed_{city_slug}"
    city_id = f"city_{city_slug}"
    player_progress_id = f"player_progress_{city_slug}"

    district_ids = sorted(district.id for district in seed.district_configuration.districts)
    faction_ids = sorted(faction.id for faction in seed.faction_configuration.factions)
    case_ids = sorted(case.id for case in seed.case_configuration.cases)
    npc_ids = sorted(npc.id for npc in seed.npc_configuration.npcs)
    lantern_ids = [f"lantern_{district_id}" for district_id in district_ids]

    objects_to_save = [
        _build_city_seed(seed, city_seed_id, district_ids, faction_ids, case_ids, npc_ids)
    ]

    for district in seed.district_configuration.districts:
        objects_to_save.append(_build_district_state(seed, district.id))
        objects_to_save.append(_build_lantern_state(seed, district.id))

    for faction in seed.faction_configuration.factions:
        objects_to_save.append(_build_faction_state(seed, faction.id))

    for case in seed.case_configuration.cases:
        objects_to_save.append(_build_case_state(seed, case.id))

    for npc in seed.npc_configuration.npcs:
        objects_to_save.append(_build_npc_state(seed, npc.id))

    objects_to_save.append(_build_player_progress_state(seed, player_progress_id))
    objects_to_save.append(
        _build_city_state(seed, city_id, city_seed_id, district_ids, faction_ids, case_ids)
    )

    store.save_objects_atomically(objects_to_save)

    return BootstrapResult(
        city_seed_id=city_seed_id,
        city_id=city_id,
        player_progress_id=player_progress_id,
        district_ids=district_ids,
        faction_ids=faction_ids,
        lantern_ids=lantern_ids,
        case_ids=case_ids,
        npc_ids=npc_ids,
    )


def _build_city_seed(
    seed: CitySeedDocument,
    city_seed_id: str,
    district_ids: list[str],
    faction_ids: list[str],
    case_ids: list[str],
    npc_ids: list[str],
) -> CitySeed:
    city_identity = seed.city_identity
    return CitySeed(
        id=city_seed_id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        city_premise=_build_city_premise(seed),
        dominant_mood=city_identity.dominant_mood,
        district_ids=district_ids,
        faction_ids=faction_ids,
        starting_cases=case_ids,
        initial_missingness_pressure=seed.missingness_configuration.missingness_pressure,
        initial_lantern_profile={
            district.id: district.lantern_state
            for district in seed.district_configuration.districts
        },
        key_npc_ids=npc_ids,
    )


def _build_city_state(
    seed: CitySeedDocument,
    city_id: str,
    city_seed_id: str,
    district_ids: list[str],
    faction_ids: list[str],
    case_ids: list[str],
) -> CityState:
    return CityState(
        id=city_id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        city_seed_id=city_seed_id,
        time_index=0,
        global_tension=_initial_global_tension(seed),
        civic_trust=_initial_civic_trust(seed),
        missingness_pressure=seed.missingness_configuration.missingness_pressure,
        active_case_ids=case_ids,
        district_ids=district_ids,
        faction_ids=faction_ids,
        player_presence_level=0.0,
    )


def _build_district_state(seed: CitySeedDocument, district_id: str) -> DistrictState:
    district = _district_by_id(seed, district_id)
    return DistrictState(
        id=district.id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        name=district.name,
        tone=district.role,
        stability=district.stability_baseline,
        lantern_condition=district.lantern_state,
        governing_power=_governing_faction_id(seed, district.id),
        relevant_npc_ids=sorted(
            npc.id for npc in seed.npc_configuration.npcs if npc.district_id == district.id
        ),
        current_access_level=district.access_pattern,
    )


def _build_faction_state(seed: CitySeedDocument, faction_id: str) -> FactionState:
    faction = _faction_by_id(seed, faction_id)
    return FactionState(
        id=faction.id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        name=faction.name,
        public_goal=faction.public_goal,
        hidden_goal=faction.hidden_goal,
        influence_by_district=dict(faction.influence_by_district),
        tension_with_other_factions=_tension_map_for_faction(seed, faction.id),
        attitude_toward_player=faction.attitude_toward_player,
        known_assets=[faction.role],
    )


def _build_lantern_state(seed: CitySeedDocument, district_id: str) -> LanternState:
    district = _district_by_id(seed, district_id)
    lantern_configuration = seed.lantern_configuration
    return LanternState(
        id=f"lantern_{district.id}",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        scope_type="district",
        scope_id=district.id,
        owner_faction=_governing_faction_id(seed, district.id),
        maintainer_group=lantern_configuration.lantern_maintenance_structure,
        condition_state=district.lantern_state,
        reach_scope_notes=lantern_configuration.lantern_reach_profile,
        social_effects=list(lantern_configuration.lantern_social_effect_profile),
        memory_effects=list(lantern_configuration.lantern_memory_effect_profile),
        access_effects=[district.access_pattern],
        anomaly_flags=_lantern_anomaly_flags(seed, district.lantern_state),
    )


def _build_case_state(seed: CitySeedDocument, case_id: str) -> CaseState:
    case = _case_by_id(seed, case_id)
    return CaseState(
        id=case.id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        title=_humanize_identifier(case.id, prefix="case_"),
        case_type=case.type,
        status="latent",
        involved_district_ids=list(case.involved_district_ids),
        involved_npc_ids=list(case.key_npc_ids),
        involved_faction_ids=list(case.involved_faction_ids),
        open_questions=list(case.failure_modes),
        objective_summary=f"Resolve a {case.intensity} {case.type} case with {case.scope} scope.",
    )


def _build_npc_state(seed: CitySeedDocument, npc_id: str) -> NPCState:
    npc = _npc_by_id(seed, npc_id)
    return NPCState(
        id=npc.id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        name=npc.name,
        role_category=npc.role_category,
        district_id=npc.district_id,
        location_id=npc.location_id,
        public_identity=npc.role_category,
        hidden_objective=f"Protect secrets with {npc.secrecy_level} exposure risk.",
        current_objective=f"Maintain {npc.mobility_pattern} routine.",
        loyalty=_governing_faction_id(seed, npc.district_id),
        relationship_flags=[npc.relationship_density, npc.memory_depth, npc.secrecy_level],
        relationships={
            "player": RelationshipSnapshot(
                trust=0.0,
                suspicion=0.0,
                fear=0.0,
                status="unknown",
                last_updated_at=TURN_ZERO,
            )
        },
        schedule_anchor=npc.location_id or npc.district_id or "",
        offscreen_state="idle",
        relevance_rating=RELEVANCE_RATINGS.get(npc.relevance_level, 0.5),
    )


def _build_player_progress_state(
    seed: CitySeedDocument, player_progress_id: str
) -> PlayerProgressState:
    start = seed.progression_start_state
    scores = {
        "lantern_understanding": start.starting_lantern_understanding,
        "access": start.starting_access,
        "reputation": start.starting_reputation,
        "leverage": start.starting_leverage,
        "city_impact": start.starting_city_impact,
        "clue_mastery": start.starting_clue_mastery,
    }
    return PlayerProgressState(
        id=player_progress_id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        **{
            track: ScoreTier(score=score, tier=get_tier_label(track, get_tier(score)))
            for track, score in scores.items()
        },
    )


def _district_by_id(seed: CitySeedDocument, district_id: str):
    for district in seed.district_configuration.districts:
        if district.id == district_id:
            return district
    raise KeyError(district_id)


def _faction_by_id(seed: CitySeedDocument, faction_id: str):
    for faction in seed.faction_configuration.factions:
        if faction.id == faction_id:
            return faction
    raise KeyError(faction_id)


def _case_by_id(seed: CitySeedDocument, case_id: str):
    for case in seed.case_configuration.cases:
        if case.id == case_id:
            return case
    raise KeyError(case_id)


def _npc_by_id(seed: CitySeedDocument, npc_id: str):
    for npc in seed.npc_configuration.npcs:
        if npc.id == npc_id:
            return npc
    raise KeyError(npc_id)


def _build_city_premise(seed: CitySeedDocument) -> str:
    mood = ", ".join(seed.city_identity.dominant_mood)
    return (
        f"{seed.city_identity.city_name} is a {mood} city shaped by "
        f"{seed.missingness_configuration.missingness_style}."
    )


def _initial_global_tension(seed: CitySeedDocument) -> float:
    tension_values = list(seed.faction_configuration.tension_map.values())
    if not tension_values:
        return seed.missingness_configuration.missingness_pressure
    return round(sum(tension_values) / len(tension_values), 2)


def _initial_civic_trust(seed: CitySeedDocument) -> float:
    return round(1.0 - seed.missingness_configuration.missingness_pressure, 2)


def _governing_faction_id(seed: CitySeedDocument, district_id: str) -> str | None:
    highest_influence = 0.0
    governing_faction_id: str | None = None
    for faction in sorted(seed.faction_configuration.factions, key=lambda item: item.id):
        influence = faction.influence_by_district.get(district_id, 0.0)
        if influence > highest_influence:
            highest_influence = influence
            governing_faction_id = faction.id
    return governing_faction_id


def _tension_map_for_faction(seed: CitySeedDocument, faction_id: str) -> dict[str, float]:
    tensions: dict[str, float] = {}
    for key, value in seed.faction_configuration.tension_map.items():
        left, _, right = key.partition("|")
        if left == faction_id:
            tensions[right] = value
        elif right == faction_id:
            tensions[left] = value
    return tensions


def _lantern_anomaly_flags(seed: CitySeedDocument, lantern_state: str) -> list[str]:
    if lantern_state in {"altered", "extinguished"}:
        return ["seeded_instability"]
    if seed.lantern_configuration.lantern_tampering_probability >= 0.5:
        return ["elevated_tampering_risk"]
    return []



def _humanize_identifier(value: str, *, prefix: str = "") -> str:
    normalized = value[len(prefix) :] if prefix and value.startswith(prefix) else value
    words = normalized.split("_")
    return " ".join(word.capitalize() for word in words if word)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "city"


__all__ = ["BootstrapResult", "bootstrap_city"]
