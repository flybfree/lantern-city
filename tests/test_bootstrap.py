from __future__ import annotations

from lantern_city.bootstrap import BootstrapResult, bootstrap_city
from lantern_city.models import (
    CaseState,
    CityState,
    DistrictState,
    FactionState,
    LanternState,
    NPCState,
    PlayerProgressState,
)
from lantern_city.seed_schema import validate_city_seed
from lantern_city.store import SQLiteStore


def make_valid_seed_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "city_identity": {
            "city_name": "Lantern City",
            "dominant_mood": ["noir", "wet", "uncertain"],
            "weather_pattern": ["persistent rain", "coastal fog"],
            "architectural_style": ["old stone", "brass fixtures", "narrow alleys"],
            "economic_character": ["port trade", "recordkeeping", "repair labor"],
            "social_texture": ["guarded", "rumor-driven", "hierarchy-conscious"],
            "ritual_texture": ["formal lantern ceremonies", "hidden shrine practice"],
            "baseline_noise_level": "medium",
        },
        "district_configuration": {
            "district_count": 2,
            "districts": [
                {
                    "id": "district_old_quarter",
                    "name": "Old Quarter",
                    "role": "memory/archive district",
                    "stability_baseline": 0.47,
                    "lantern_state": "dim",
                    "access_pattern": "restricted",
                    "hidden_location_density": "medium",
                },
                {
                    "id": "district_lantern_ward",
                    "name": "Lantern Ward",
                    "role": "administrative lantern district",
                    "stability_baseline": 0.71,
                    "lantern_state": "bright",
                    "access_pattern": "controlled",
                    "hidden_location_density": "low",
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
                    },
                    "attitude_toward_player": "wary",
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
                    },
                    "attitude_toward_player": "guarded",
                },
            ],
            "tension_map": {
                "faction_memory_keepers|faction_council_lights": 0.58,
            },
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
        },
        "missingness_configuration": {
            "missingness_pressure": 0.42,
            "missingness_scope": "records first",
            "missingness_visibility": "known-but-denied",
            "missingness_style": "edited records and contradictory witness accounts",
            "missingness_targets": ["families", "archives"],
            "missingness_risk_level": "medium",
        },
        "case_configuration": {
            "starting_case_count": 1,
            "cases": [
                {
                    "id": "case_missing_clerk",
                    "type": "missing person",
                    "intensity": "medium",
                    "scope": "single district",
                    "involved_district_ids": ["district_old_quarter"],
                    "involved_faction_ids": ["faction_memory_keepers"],
                    "key_npc_ids": ["npc_shrine_keeper", "npc_archive_clerk"],
                    "failure_modes": ["evidence destroyed", "Missingness escalates"],
                }
            ],
        },
        "npc_configuration": {
            "tracked_npc_count": 2,
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
                    "role_category": "witness",
                    "district_id": "district_old_quarter",
                    "location_id": "location_archive_steps",
                    "memory_depth": "high",
                    "relationship_density": "medium",
                    "secrecy_level": "medium",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "immediate",
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
        },
    }


def make_valid_seed_document():
    return validate_city_seed(make_valid_seed_payload())


def test_bootstrap_city_persists_expected_world_objects(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")

    result = bootstrap_city(make_valid_seed_document(), store)

    assert isinstance(result, BootstrapResult)
    assert store.load_object("CityState", result.city_id) is not None
    assert store.load_object("PlayerProgressState", result.player_progress_id) is not None
    assert len(store.list_objects("DistrictState")) == 2
    assert len(store.list_objects("FactionState")) == 2
    assert len(store.list_objects("LanternState")) == 2
    assert len(store.list_objects("CaseState")) == 1
    assert len(store.list_objects("NPCState")) == 2


def test_bootstrap_city_preserves_seed_ids_and_relationships(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")

    result = bootstrap_city(make_valid_seed_document(), store)
    city = store.load_object("CityState", result.city_id)
    districts = store.list_objects("DistrictState")
    factions = store.list_objects("FactionState")
    lanterns = store.list_objects("LanternState")
    cases = store.list_objects("CaseState")
    npcs = store.list_objects("NPCState")

    assert isinstance(city, CityState)
    assert city.district_ids == ["district_lantern_ward", "district_old_quarter"]
    assert city.faction_ids == ["faction_council_lights", "faction_memory_keepers"]
    assert city.active_case_ids == ["case_missing_clerk"]

    assert [district.id for district in districts] == [
        "district_lantern_ward",
        "district_old_quarter",
    ]
    assert [faction.id for faction in factions] == [
        "faction_council_lights",
        "faction_memory_keepers",
    ]
    assert [lantern.id for lantern in lanterns] == [
        "lantern_district_lantern_ward",
        "lantern_district_old_quarter",
    ]
    assert [case.id for case in cases] == ["case_missing_clerk"]
    assert [npc.id for npc in npcs] == ["npc_archive_clerk", "npc_shrine_keeper"]

    old_quarter = next(district for district in districts if district.id == "district_old_quarter")
    assert old_quarter.relevant_npc_ids == ["npc_archive_clerk", "npc_shrine_keeper"]
    assert old_quarter.governing_power == "faction_memory_keepers"

    active_case = cases[0]
    assert active_case.involved_district_ids == ["district_old_quarter"]
    assert active_case.involved_npc_ids == ["npc_shrine_keeper", "npc_archive_clerk"]
    assert active_case.involved_faction_ids == ["faction_memory_keepers"]


def test_bootstrap_city_initializes_player_progress_from_seed(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")

    result = bootstrap_city(make_valid_seed_document(), store)
    progress = store.load_object("PlayerProgressState", result.player_progress_id)

    assert isinstance(progress, PlayerProgressState)
    assert progress.lantern_understanding.score == 18
    assert progress.access.score == 10
    assert progress.reputation.score == 12
    assert progress.leverage.score == 5
    assert progress.city_impact.score == 2
    assert progress.clue_mastery.score == 20


def test_bootstrap_city_loads_back_usable_runtime_models(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")

    result = bootstrap_city(make_valid_seed_document(), store)

    city = store.load_object("CityState", result.city_id)
    district = store.load_object("DistrictState", "district_old_quarter")
    faction = store.load_object("FactionState", "faction_memory_keepers")
    lantern = store.load_object("LanternState", "lantern_district_old_quarter")
    case = store.load_object("CaseState", "case_missing_clerk")
    npc = store.load_object("NPCState", "npc_shrine_keeper")
    progress = store.load_object("PlayerProgressState", result.player_progress_id)

    assert isinstance(city, CityState)
    assert isinstance(district, DistrictState)
    assert isinstance(faction, FactionState)
    assert isinstance(lantern, LanternState)
    assert isinstance(case, CaseState)
    assert isinstance(npc, NPCState)
    assert isinstance(progress, PlayerProgressState)

    assert city.missingness_pressure == 0.42
    assert district.lantern_condition == "dim"
    assert faction.attitude_toward_player == "wary"
    assert lantern.scope_id == "district_old_quarter"
    assert case.status == "active"
    assert npc.location_id == "location_shrine_lane"
