from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from lantern_city.generation.city_seed import (
    CitySeedGenerationError,
    CitySeedGenerationRequest,
    CitySeedGenerator,
)


class StubLLMClient:
    def __init__(
        self,
        payload: dict[str, object] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, object]] = []

    def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        schema: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "schema": schema,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.payload is not None
        return self.payload


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


def test_city_seed_generator_builds_narrow_request_and_returns_validated_seed() -> None:
    payload = make_valid_seed_payload()
    client = StubLLMClient(payload)
    generator = CitySeedGenerator(client)

    result = generator.generate(
        CitySeedGenerationRequest(
            request_id="req_city_seed_001",
            city_scale="mvp",
            seed_parameters={"district_count": 2, "faction_count": 2},
        )
    )

    assert result.schema_version == "1.0"
    assert result.city_identity.city_name == "Lantern City"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 2400
    assert call["schema"] is not None
    assert call["schema"]["type"] == "object"
    assert "properties" in call["schema"]
    messages = call["messages"]
    assert messages[0]["role"] == "system"
    assert "engine owns all persistent state" in messages[0]["content"].lower()
    assert "task_type\": \"city_seed\"" in messages[1]["content"]
    assert "request_id\": \"req_city_seed_001\"" in messages[1]["content"]
    assert "district_count" in messages[1]["content"]
    assert "JSON Schema" in messages[1]["content"]
    assert '"city_identity"' in messages[1]["content"]
    assert '"district_configuration"' in messages[1]["content"]


def test_city_seed_generator_wraps_invalid_json_errors() -> None:
    client = StubLLMClient(error=ValueError("invalid JSON from model"))
    generator = CitySeedGenerator(client)

    with pytest.raises(CitySeedGenerationError, match="invalid JSON from model"):
        generator.generate(CitySeedGenerationRequest(request_id="req_city_seed_002"))


def test_city_seed_generator_propagates_schema_validation_failure() -> None:
    payload = copy.deepcopy(make_valid_seed_payload())
    payload["district_configuration"]["district_count"] = 99
    client = StubLLMClient(payload)
    generator = CitySeedGenerator(client)

    with pytest.raises(ValidationError, match="district_count"):
        generator.generate(CitySeedGenerationRequest(request_id="req_city_seed_003"))


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        pytest.param(
            {"request_id": "   "},
            "request_id must be a non-empty string",
            id="blank-request-id",
        ),
        pytest.param(
            {"request_id": "req_city_seed_004", "seed_parameters": {"bad": object()}},
            "seed_parameters must be JSON-serializable",
            id="non-serializable-seed-parameters",
        ),
        pytest.param(
            {"request_id": "req_city_seed_005", "seed_parameters": {1: "bad key"}},
            "seed_parameters keys must be strings",
            id="non-string-seed-parameter-key",
        ),
    ],
)
def test_city_seed_generation_request_rejects_invalid_inputs(
    kwargs: dict[str, object], expected_message: str
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        CitySeedGenerationRequest(**kwargs)


def test_city_seed_generation_request_preserves_json_safe_payload() -> None:
    request = CitySeedGenerationRequest(
        request_id="req_city_seed_006",
        seed_parameters={"district_count": 2, "tags": ["wet", "noir"]},
    )

    assert json.loads(request.to_json()) == {
        "city_scale": "mvp",
        "request_id": "req_city_seed_006",
        "schema_version": "1.0",
        "seed_parameters": {"district_count": 2, "tags": ["wet", "noir"]},
    }


def test_city_seed_generator_rejects_client_without_generate_json() -> None:
    with pytest.raises(TypeError, match="generate_json"):
        CitySeedGenerator(object())
