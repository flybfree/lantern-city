from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from lantern_city.generation.city_seed import (
    CitySeedGenerationError,
    CitySeedGenerationRequest,
    CitySeedGenerator,
)


# ── Stub LLM client ───────────────────────────────────────────────────────────

class StubLLMClient:
    """Returns payloads from a queue — one per generate_json call."""

    def __init__(
        self,
        payloads: list[dict[str, object]] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._payloads = list(payloads or [])
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
        self.calls.append({
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "schema": schema,
        })
        if self.error is not None:
            raise self.error
        assert self._payloads, "StubLLMClient ran out of payloads"
        return self._payloads.pop(0)


# ── Fixture payloads ──────────────────────────────────────────────────────────

def _framework_payload() -> dict[str, object]:
    return {
        "city_name": "Velmoor",
        "dominant_mood": ["noir", "damp", "suspicious"],
        "weather_pattern": ["coastal fog"],
        "architectural_style": ["stone facades"],
        "economic_character": ["port trade"],
        "social_texture": ["guarded"],
        "ritual_texture": ["lantern vigils"],
        "baseline_noise_level": "medium",
        "districts": [
            {
                "id": "district_old_quarter",
                "name": "Old Quarter",
                "role": "archive district",
                "stability_baseline": 0.47,
                "lantern_state": "dim",
                "access_pattern": "restricted",
                "hidden_location_density": "medium",
            },
            {
                "id": "district_lantern_ward",
                "name": "Lantern Ward",
                "role": "administrative district",
                "stability_baseline": 0.71,
                "lantern_state": "bright",
                "access_pattern": "controlled",
                "hidden_location_density": "low",
            },
        ],
        "factions": [
            {
                "id": "faction_memory_keepers",
                "name": "Memory Keepers",
                "role": "memory stewardship",
                "public_goal": "preserve continuity",
                "hidden_goal": "control memory",
                "influence_by_district": {
                    "district_old_quarter": 0.78,
                    "district_lantern_ward": 0.22,
                },
                "attitude_toward_player": "wary",
            },
            {
                "id": "faction_council_lights",
                "name": "Council of Lights",
                "role": "civic lantern admin",
                "public_goal": "maintain order",
                "hidden_goal": "monopolize lanterns",
                "influence_by_district": {
                    "district_old_quarter": 0.18,
                    "district_lantern_ward": 0.81,
                },
                "attitude_toward_player": "guarded",
            },
        ],
        "tension_map": {"faction_memory_keepers|faction_council_lights": 0.58},
        "lantern_system_style": "civic grid",
        "lantern_ownership_structure": "mixed",
        "lantern_maintenance_structure": "civic engineers",
        "lantern_condition_distribution": {
            "bright": 0.40,
            "dim": 0.35,
            "flickering": 0.15,
            "extinguished": 0.05,
            "altered": 0.05,
        },
        "lantern_reach_profile": "district-wide",
        "lantern_social_effect_profile": ["legitimacy"],
        "lantern_memory_effect_profile": ["clearer testimony"],
        "lantern_tampering_probability": 0.22,
        "missingness_pressure": 0.42,
        "missingness_scope": "records first",
        "missingness_visibility": "known-but-denied",
        "missingness_style": "edited records",
        "missingness_targets": ["archives"],
        "missingness_risk_level": "medium",
        "story_density": "medium",
        "mystery_complexity": "medium",
        "social_resistance": "medium",
        "investigation_pace": "deliberate",
        "consequence_severity": "medium",
        "revelation_delay": "gradual",
        "narrative_strangeness": "grounded",
    }


def _cases_npcs_payload() -> dict[str, object]:
    return {
        "cases": [
            {
                "id": "case_missing_clerk",
                "type": "missing person",
                "intensity": "medium",
                "scope": "single district",
                "involved_district_ids": ["district_old_quarter"],
                "involved_faction_ids": ["faction_memory_keepers"],
                "key_npc_ids": ["npc_shrine_keeper", "npc_archive_clerk"],
                "failure_modes": ["evidence destroyed"],
            }
        ],
        "npcs": [
            {
                "id": "npc_shrine_keeper",
                "name": "Ila Venn",
                "role_category": "informant",
                "district_id": "district_old_quarter",
                "location_id": "location_tbd",
                "memory_depth": "medium",
                "relationship_density": "medium",
                "secrecy_level": "high",
                "mobility_pattern": "district-bound",
                "relevance_level": "immediate",
            },
            {
                "id": "npc_archive_clerk",
                "name": "Sered Marr",
                "role_category": "gatekeeper",
                "district_id": "district_old_quarter",
                "location_id": "location_tbd",
                "memory_depth": "high",
                "relationship_density": "medium",
                "secrecy_level": "high",
                "mobility_pattern": "district-bound",
                "relevance_level": "immediate",
            },
        ],
        "starting_lantern_understanding": 18,
        "starting_access": 10,
        "starting_reputation": 12,
        "starting_leverage": 5,
        "starting_city_impact": 2,
        "starting_clue_mastery": 20,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_city_seed_generator_makes_two_calls_and_returns_validated_seed() -> None:
    client = StubLLMClient(payloads=[_framework_payload(), _cases_npcs_payload()])
    generator = CitySeedGenerator(client)

    result = generator.generate(CitySeedGenerationRequest(request_id="req_001"))

    assert result.schema_version == "1.0"
    assert result.city_identity.city_name == "Velmoor"
    assert len(client.calls) == 2

    # Phase 1 call
    call1 = client.calls[0]
    assert call1["schema"] is not None
    assert "city_name" in str(call1["schema"])
    assert call1["messages"][0]["role"] == "system"

    # Phase 2 call — district IDs injected as context
    call2 = client.calls[1]
    assert "district_old_quarter" in call2["messages"][1]["content"]
    assert "faction_memory_keepers" in call2["messages"][1]["content"]


def test_city_seed_generator_raises_on_framework_llm_error() -> None:
    client = StubLLMClient(error=ValueError("network timeout"))
    generator = CitySeedGenerator(client)

    with pytest.raises(CitySeedGenerationError, match="network timeout"):
        generator.generate(CitySeedGenerationRequest(request_id="req_002"))


def test_city_seed_generator_remaps_bad_npc_district_id() -> None:
    # Assembly now coerces bad district IDs to the nearest valid one rather than raising.
    bad_cases_npcs = _cases_npcs_payload()
    bad_cases_npcs["npcs"][0]["district_id"] = "district_does_not_exist"  # type: ignore[index]
    client = StubLLMClient(payloads=[_framework_payload(), bad_cases_npcs])
    generator = CitySeedGenerator(client)

    # Should succeed: the bad district_id is remapped to the first valid district
    result = generator.generate(CitySeedGenerationRequest(request_id="req_003"))
    valid_ids = {d.id for d in result.district_configuration.districts}
    for npc in result.npc_configuration.npcs:
        assert npc.district_id in valid_ids, f"NPC {npc.name} has invalid district_id {npc.district_id}"


def test_city_seed_generator_raises_on_truly_broken_payload() -> None:
    # Truly broken payloads (e.g. empty districts list) still raise CitySeedGenerationError.
    broken_framework = _framework_payload()
    broken_framework["districts"] = []  # no districts → schema requires at least 1
    client = StubLLMClient(payloads=[broken_framework, _cases_npcs_payload()])
    generator = CitySeedGenerator(client)

    with pytest.raises(CitySeedGenerationError, match="Seed validation failed"):
        generator.generate(CitySeedGenerationRequest(request_id="req_003b"))


def test_city_seed_generation_request_rejects_blank_request_id() -> None:
    with pytest.raises(ValueError, match="request_id must be non-empty"):
        CitySeedGenerationRequest(request_id="   ")


def test_city_seed_generation_request_concept_is_optional() -> None:
    req = CitySeedGenerationRequest(request_id="req_004")
    assert req.concept == ""

    req_with_concept = CitySeedGenerationRequest(
        request_id="req_005", concept="A harbor city under military occupation"
    )
    assert req_with_concept.concept == "A harbor city under military occupation"


def test_city_seed_generator_rejects_client_without_generate_json() -> None:
    with pytest.raises(TypeError, match="generate_json"):
        CitySeedGenerator(object())


def test_city_seed_generator_concept_appears_in_framework_prompt() -> None:
    client = StubLLMClient(payloads=[_framework_payload(), _cases_npcs_payload()])
    generator = CitySeedGenerator(client)

    generator.generate(CitySeedGenerationRequest(
        request_id="req_006",
        concept="A city built on competing guilds and river trade",
    ))

    assert "A city built on competing guilds" in client.calls[0]["messages"][1]["content"]
    assert "A city built on competing guilds" in client.calls[1]["messages"][1]["content"]


def test_city_seed_generator_normalizes_distribution_to_sum_to_one() -> None:
    framework = _framework_payload()
    # Intentionally off-sum distribution
    framework["lantern_condition_distribution"] = {
        "bright": 0.5,
        "dim": 0.5,
        "flickering": 0.5,
        "extinguished": 0.5,
        "altered": 0.5,
    }
    client = StubLLMClient(payloads=[framework, _cases_npcs_payload()])
    generator = CitySeedGenerator(client)

    result = generator.generate(CitySeedGenerationRequest(request_id="req_007"))
    dist = result.lantern_configuration.lantern_condition_distribution
    assert abs(sum(dist.values()) - 1.0) < 0.01
