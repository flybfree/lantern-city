from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from lantern_city.seed_schema import validate_city_seed


@pytest.fixture
def valid_seed_payload() -> dict[str, object]:
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


def test_validate_city_seed_accepts_documented_shape(valid_seed_payload: dict[str, object]) -> None:
    validated = validate_city_seed(valid_seed_payload)

    assert validated.schema_version == "1.0"
    assert validated.city_identity.city_name == "Lantern City"
    assert validated.district_configuration.district_count == len(
        validated.district_configuration.districts
    )
    assert validated.case_configuration.cases[0].key_npc_ids == [
        "npc_shrine_keeper",
        "npc_archive_clerk",
    ]


def test_validate_city_seed_allows_long_dominant_mood_entries(
    valid_seed_payload: dict[str, object],
) -> None:
    payload = copy.deepcopy(valid_seed_payload)
    payload["city_identity"]["dominant_mood"] = [
        "oppressively ceremonial and haunted by procedural memory",
        "rain-soaked and politically exhausted after years of managed forgetting",
    ]

    validated = validate_city_seed(payload)

    assert validated.city_identity.dominant_mood == payload["city_identity"]["dominant_mood"]


def test_validate_city_seed_allows_duplicate_npc_names(
    valid_seed_payload: dict[str, object],
) -> None:
    payload = copy.deepcopy(valid_seed_payload)
    payload["npc_configuration"]["npcs"][1]["name"] = payload["npc_configuration"]["npcs"][0]["name"]

    validated = validate_city_seed(payload)

    assert [npc.name for npc in validated.npc_configuration.npcs] == ["Ila Venn", "Ila Venn"]


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        pytest.param(
            lambda payload: payload.pop("npc_configuration"),
            "npc_configuration",
            id="missing-required-top-level-key",
        ),
        pytest.param(
            lambda payload: payload["city_identity"].__setitem__("city_name", ""),
            "city_name",
            id="empty-city-name",
        ),
        pytest.param(
            lambda payload: payload["city_identity"].__setitem__("dominant_mood", ["only_one"]),
            "dominant_mood",
            id="dominant-mood-too-short",
        ),
        pytest.param(
            lambda payload: payload["city_identity"].__setitem__("baseline_noise_level", "loud"),
            "baseline_noise_level",
            id="invalid-noise-enum",
        ),
        pytest.param(
            lambda payload: payload["district_configuration"].__setitem__("district_count", 3),
            "district_count",
            id="district-count-mismatch",
        ),
        pytest.param(
            lambda payload: payload["district_configuration"]["districts"][1].__setitem__(
                "id", payload["district_configuration"]["districts"][0]["id"]
            ),
            "unique district id",
            id="duplicate-district-id",
        ),
        pytest.param(
            lambda payload: payload["district_configuration"]["districts"][0].__setitem__(
                "stability_baseline", 1.2
            ),
            "stability_baseline",
            id="district-stability-out-of-range",
        ),
        pytest.param(
            lambda payload: payload["district_configuration"]["districts"][0].__setitem__(
                "lantern_state", "broken"
            ),
            "lantern_state",
            id="invalid-district-lantern-state",
        ),
        pytest.param(
            lambda payload: payload["faction_configuration"].__setitem__("faction_count", 1),
            "faction_count",
            id="faction-count-mismatch",
        ),
        pytest.param(
            lambda payload: payload["faction_configuration"].__setitem__(
                "tension_map", {"not-a-pair": 0.2}
            ),
            "tension_map",
            id="invalid-tension-map-key-format",
        ),
        pytest.param(
            lambda payload: payload["lantern_configuration"].__setitem__(
                "lantern_condition_distribution",
                {
                    "bright": 0.6,
                    "dim": 0.35,
                    "flickering": 0.15,
                    "extinguished": 0.05,
                    "altered": 0.05,
                },
            ),
            "lantern_condition_distribution",
            id="lantern-distribution-does-not-sum-to-one",
        ),
        pytest.param(
            lambda payload: payload["lantern_configuration"].__setitem__(
                "lantern_tampering_probability", -0.1
            ),
            "lantern_tampering_probability",
            id="lantern-tampering-out-of-range",
        ),
        pytest.param(
            lambda payload: payload["missingness_configuration"].__setitem__(
                "missingness_pressure", 1.1
            ),
            "missingness_pressure",
            id="missingness-pressure-out-of-range",
        ),
        pytest.param(
            lambda payload: payload["missingness_configuration"].__setitem__(
                "missingness_risk_level", "severe"
            ),
            "missingness_risk_level",
            id="invalid-missingness-risk-level",
        ),
        pytest.param(
            lambda payload: payload["case_configuration"].__setitem__("starting_case_count", 2),
            "starting_case_count",
            id="starting-case-count-mismatch",
        ),
        pytest.param(
            lambda payload: payload["case_configuration"]["cases"][0].__setitem__(
                "involved_district_ids", ["district_unknown"]
            ),
            "district_unknown",
            id="case-references-unknown-district",
        ),
        pytest.param(
            lambda payload: payload["case_configuration"]["cases"][0].__setitem__(
                "involved_faction_ids", ["faction_unknown"]
            ),
            "faction_unknown",
            id="case-references-unknown-faction",
        ),
        pytest.param(
            lambda payload: payload["case_configuration"]["cases"][0].__setitem__(
                "key_npc_ids", ["npc_unknown"]
            ),
            "npc_unknown",
            id="case-references-unknown-npc",
        ),
        pytest.param(
            lambda payload: payload["npc_configuration"].__setitem__("tracked_npc_count", 1),
            "tracked_npc_count",
            id="tracked-npc-count-below-detailed-record-count",
        ),
        pytest.param(
            lambda payload: payload["npc_configuration"].__setitem__("tracked_npc_count", 3),
            "tracked_npc_count",
            id="tracked-npc-count-above-detailed-record-count",
        ),
        pytest.param(
            lambda payload: payload["npc_configuration"]["npcs"][0].__setitem__(
                "district_id", "district_unknown"
            ),
            "district_unknown",
            id="npc-references-unknown-district",
        ),
        pytest.param(
            lambda payload: payload["progression_start_state"].__setitem__(
                "starting_access", 101
            ),
            "starting_access",
            id="progression-out-of-range",
        ),
    ],
)
def test_validate_city_seed_rejects_invalid_payloads(
    valid_seed_payload: dict[str, object],
    mutator,
    match: str,
) -> None:
    payload = copy.deepcopy(valid_seed_payload)
    mutator(payload)

    with pytest.raises(ValidationError, match=match):
        validate_city_seed(payload)
