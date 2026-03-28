from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from lantern_city.active_slice import ActiveSlice
from lantern_city.generation.district import (
    DistrictGenerationError,
    DistrictGenerationRequest,
    DistrictGenerationResult,
    DistrictGenerator,
)
from lantern_city.models import (
    ActiveWorkingSet,
    CaseState,
    CityState,
    DistrictState,
    NPCState,
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


def make_active_slice() -> ActiveSlice:
    city = CityState(
        id="city_001",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        city_seed_id="seed_001",
        district_ids=["district_old_quarter"],
        summary_cache={"city_identity_summary": "A wet civic maze where lantern light makes memory arguable."},
    )
    district = DistrictState(
        id="district_old_quarter",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        name="Old Quarter",
        tone="hushed and procedural",
        lantern_condition="dim",
        governing_power="faction_memory_keepers",
        active_problems=["records are going missing from local offices"],
        visible_locations=["location_archive_steps"],
        relevant_npc_ids=["npc_ila_venn"],
        rumor_pool=["Someone is editing the ledgers after dusk."],
        current_access_level="restricted",
    )
    npc = NPCState(
        id="npc_ila_venn",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        name="Ila Venn",
        role_category="shrine keeper",
        district_id="district_old_quarter",
        public_identity="Keeps the ward lantern records in good order.",
        current_objective="Keep outsiders away from the damaged ledgers.",
    )
    case = CaseState(
        id="case_missing_clerk",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        title="The Missing Clerk",
        case_type="missing person",
        status="open",
        involved_district_ids=["district_old_quarter"],
        involved_npc_ids=["npc_ila_venn"],
        open_questions=["Who altered the file trail?"],
        objective_summary="Find the missing records clerk before the trail closes.",
    )
    working_set = ActiveWorkingSet(
        id="aws_001",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        city_id=city.id,
        district_id=district.id,
        case_id=case.id,
        npc_ids=[npc.id],
    )
    return ActiveSlice(
        city=city,
        working_set=working_set,
        district=district,
        location=None,
        scene=None,
        npcs=[npc],
        clues=[],
        case=case,
    )


def make_valid_payload() -> dict[str, object]:
    return {
        "task_type": "district_expand",
        "request_id": "req_district_001",
        "summary_text": "Old Quarter arrives as a narrow district slice with one clear local pressure.",
        "structured_updates": {
            "district_summary": "Old Quarter is a damp archive ward where routine still matters more than comfort.",
            "major_locations": [
                {
                    "location_id": "location_archive_steps",
                    "name": "Archive Steps",
                    "location_type": "archive entrance",
                    "short_description": "Clerks and petitioners cross paths under failing lantern glass.",
                    "playable_hook": "The missing clerk was last logged here.",
                },
                {
                    "location_id": "location_shrine_lane",
                    "name": "Shrine Lane",
                    "location_type": "shrine street",
                    "short_description": "Rain gathers in the brass channels beneath the ward shrines.",
                    "playable_hook": "People who avoid the records office still pass through here.",
                },
                {
                    "location_id": "location_registry_annex",
                    "name": "Registry Annex",
                    "location_type": "records office",
                    "short_description": "A side office where corrected copies appear before anyone admits requesting them.",
                    "playable_hook": "A clerk inside may know who touched the ledgers.",
                },
            ],
            "local_problems": [
                "Record corrections are appearing without signatures.",
                "Residents no longer trust the posted lantern schedules.",
            ],
            "rumor_lines": [
                "A name can stay posted here for hours after the person has gone missing.",
                "The annex stamps papers faster on nights when the ward lantern runs dim.",
            ],
            "npc_anchor_ids_or_specs": [
                {
                    "npc_id": "npc_ila_venn",
                    "name": "Ila Venn",
                    "role": "shrine keeper",
                    "local_relevance": "Knows which records were moved after dark.",
                }
            ],
        },
        "cacheable_text": {
            "entry_text": "Old Quarter opens in damp stone, layered notices, and a lantern glow that never quite settles.",
            "short_summary": "A dim archive ward where missing records matter more than raised voices.",
        },
        "confidence": 0.84,
        "warnings": [],
    }


def test_district_generator_builds_narrow_prompt_and_returns_validated_output() -> None:
    client = StubLLMClient(make_valid_payload())
    generator = DistrictGenerator(client)

    result = generator.generate(
        DistrictGenerationRequest(
            request_id="req_district_001",
            active_slice=make_active_slice(),
            city_identity_summary="A wet civic maze where lantern light makes memory arguable.",
            faction_footprint=["Memory Keepers oversee the district archives."],
            missingness_pressure=0.42,
        )
    )

    assert result.task_type == "district_expand"
    assert result.structured_updates.major_locations[0].location_id == "location_archive_steps"
    assert result.cacheable_text.short_summary.startswith("A dim archive ward")
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 1200
    assert call["schema"] is not None
    messages = call["messages"]
    assert messages[0]["role"] == "system"
    assert "current district slice only" in messages[0]["content"].lower()
    assert "task_type\": \"district_expand\"" in messages[1]["content"]
    assert "request_id\": \"req_district_001\"" in messages[1]["content"]
    assert "Old Quarter" in messages[1]["content"]
    assert "Ila Venn" in messages[1]["content"]
    assert "The Missing Clerk" in messages[1]["content"]
    assert "JSON Schema" in messages[1]["content"]
    assert '"major_locations"' in messages[1]["content"]
    assert '"npc_anchor_ids_or_specs"' in messages[1]["content"]
    assert "district slice needed for current play" in messages[1]["content"].lower()


def test_district_generator_wraps_llm_errors() -> None:
    client = StubLLMClient(error=ValueError("provider timeout"))
    generator = DistrictGenerator(client)

    with pytest.raises(DistrictGenerationError, match="provider timeout"):
        generator.generate(
            DistrictGenerationRequest(
                request_id="req_district_002",
                active_slice=make_active_slice(),
                city_identity_summary="A wet civic maze where lantern light makes memory arguable.",
            )
        )


def test_district_generator_rejects_malformed_output() -> None:
    payload = copy.deepcopy(make_valid_payload())
    del payload["structured_updates"]["rumor_lines"]
    client = StubLLMClient(payload)
    generator = DistrictGenerator(client)

    with pytest.raises(ValidationError, match="rumor_lines"):
        generator.generate(
            DistrictGenerationRequest(
                request_id="req_district_003",
                active_slice=make_active_slice(),
                city_identity_summary="A wet civic maze where lantern light makes memory arguable.",
            )
        )


def test_district_generation_result_requires_exact_task_type() -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["task_type"] = "district_summary"

    with pytest.raises(ValidationError, match="task_type"):
        DistrictGenerationResult.model_validate(payload)


def test_district_generation_result_rejects_unbounded_location_text() -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["structured_updates"]["major_locations"][0]["short_description"] = "X" * 181

    with pytest.raises(ValidationError, match="short_description"):
        DistrictGenerationResult.model_validate(payload)


def test_district_generation_result_rejects_non_local_npc_anchor_id_shape() -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["structured_updates"]["npc_anchor_ids_or_specs"][0]["npc_id"] = "citizen_ila_venn"

    with pytest.raises(ValidationError, match="npc_id"):
        DistrictGenerationResult.model_validate(payload)


def test_district_generation_result_rejects_blank_npc_anchor_local_spec() -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["structured_updates"]["npc_anchor_ids_or_specs"][0]["npc_id"] = None
    payload["structured_updates"]["npc_anchor_ids_or_specs"][0]["local_relevance"] = "   "

    with pytest.raises(ValidationError, match="local_relevance"):
        DistrictGenerationResult.model_validate(payload)


def test_district_generation_request_requires_active_district() -> None:
    active_slice = make_active_slice()
    active_slice = ActiveSlice(
        city=active_slice.city,
        working_set=active_slice.working_set,
        district=None,
        location=active_slice.location,
        scene=active_slice.scene,
        npcs=active_slice.npcs,
        clues=active_slice.clues,
        case=active_slice.case,
    )

    with pytest.raises(ValueError, match="active district"):
        DistrictGenerationRequest(
            request_id="req_district_004",
            active_slice=active_slice,
            city_identity_summary="A wet civic maze where lantern light makes memory arguable.",
        )
