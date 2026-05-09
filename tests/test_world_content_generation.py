from __future__ import annotations

from lantern_city.generation.world_content import WorldContentGenerator
from lantern_city.models import CaseState, ClueState, DistrictState, LocationState, NPCState

TURN_ZERO = "turn_0"


class StubLLMClient:
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = list(payloads)
        self.calls: list[dict] = []

    def generate_json(self, *, messages, temperature, max_tokens, schema=None):
        self.calls.append({"messages": messages, "temperature": temperature})
        if self._payloads:
            return self._payloads.pop(0)
        return {}


def _make_district(district_id: str = "district_old_quarter") -> DistrictState:
    return DistrictState(
        id=district_id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        name="Old Quarter",
        tone="hushed and procedural",
        lantern_condition="dim",
        current_access_level="restricted",
        summary_cache={"social_rule": "speak carefully", "investigation_pressure": "records vanish"},
    )


def _make_npc(npc_id: str, district_id: str = "district_old_quarter") -> NPCState:
    return NPCState(
        id=npc_id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        name="Ila Venn",
        role_category="informant",
        district_id=district_id,
    )


def _make_case() -> CaseState:
    return CaseState(
        id="case_test_001",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        title="The Missing Record",
        case_type="missing person",
        status="latent",
        involved_district_ids=["district_old_quarter"],
        objective_summary="Find out what happened to the archive clerk.",
    )


def _make_location(loc_id: str = "location_archive_steps") -> LocationState:
    return LocationState(
        id=loc_id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        district_id="district_old_quarter",
        name="Archive Steps",
        location_type="archive",
    )


def _make_clue(clue_id: str, reliability: str = "credible") -> ClueState:
    return ClueState(
        id=clue_id,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        source_type="document",
        source_id="location_archive_steps",
        clue_text="A ledger entry has been altered.",
        reliability=reliability,
        related_case_ids=["case_test_001"],
        related_district_ids=["district_old_quarter"],
    )


def _location_payload(district_id: str = "district_old_quarter") -> dict:
    return {
        "locations": [
            {
                "id_slug": "archive_steps",
                "name": "Archive Steps",
                "location_type": "archive",
                "npc_ids": [],
                "scene_objects": ["ledger shelf", "dust-covered counter"],
                "is_hidden": False,
            }
        ]
    }


def _clue_payload() -> dict:
    return {
        "clues": [
            {
                "id_slug": "altered_ledger",
                "clue_text": "A ledger entry has been altered.",
                "source_type": "document",
                "reliability": "credible",
                "location_id": "location_archive_steps",
                "related_npc_ids": [],
            },
            {
                "id_slug": "missing_clerk_note",
                "clue_text": "A note referencing a missing clerk was tucked behind the shelf.",
                "source_type": "physical",
                "reliability": "uncertain",
                "location_id": "location_archive_steps",
                "related_npc_ids": [],
            },
        ]
    }


def _briefing_payload() -> dict:
    return {
        "title": "The Vanished Clerk",
        "discovery_hook": "Ila Venn lowers her voice. The clerk disappeared three days ago.",
        "objective_summary": "Find out what happened to the archive clerk.",
    }


def _resolution_paths_payload(clue_ids: list[str]) -> dict:
    return {
        "resolution_paths": [
            {
                "priority": 1,
                "path_id": "clean_exposure",
                "label": "Clean Exposure",
                "outcome_status": "solved",
                "required_clue_ids": clue_ids[:1],
                "required_credible_count": 1,
                "summary_text": "The truth surfaced. The case closed with the record corrected.",
                "fallout_text": "District credibility shaken. Memory Keepers under scrutiny.",
            },
            {
                "priority": 2,
                "path_id": "quiet_rescue",
                "label": "Quiet Rescue",
                "outcome_status": "partially solved",
                "required_clue_ids": [],
                "required_credible_count": 1,
                "summary_text": "The clerk was found but the institutional truth stayed buried.",
                "fallout_text": "Clerk survives. Culprits remain in place.",
            },
            {
                "priority": 3,
                "path_id": "burial",
                "label": "Burial",
                "outcome_status": "failed",
                "required_clue_ids": [],
                "required_credible_count": 0,
                "summary_text": "The investigation produced nothing before the case closed.",
                "fallout_text": "Official account hardens. Missingness pressure rises.",
            },
        ]
    }


def test_generate_produces_resolution_conditions_on_case_update() -> None:
    district = _make_district()
    npc = _make_npc("npc_ila_venn")
    case = _make_case()

    clue_ids = ["clue_test_001_altered_ledger", "clue_test_001_missing_clerk_note"]

    llm = StubLLMClient([
        _location_payload(),       # district locations
        _clue_payload(),           # case clues
        _briefing_payload(),       # case briefing
        _resolution_paths_payload(clue_ids),  # resolution paths
    ])

    gen = WorldContentGenerator(llm)
    result = gen.generate(districts=[district], npcs=[npc], cases=[case])

    assert result.case_updates, "expected at least one case update"
    updated_case = result.case_updates[0]
    assert updated_case.resolution_conditions, "resolution_conditions must be populated"
    assert len(updated_case.resolution_conditions) == 3

    priorities = [p["priority"] for p in updated_case.resolution_conditions]
    assert priorities == sorted(priorities), "paths must be sorted by priority"

    statuses = [p["outcome_status"] for p in updated_case.resolution_conditions]
    assert "solved" in statuses
    assert "failed" in statuses

    fallback = updated_case.resolution_conditions[-1]
    assert fallback["required_credible_count"] == 0, "last path must always be reachable"


def test_generate_uses_fallback_resolution_when_llm_fails() -> None:
    district = _make_district()
    npc = _make_npc("npc_ila_venn")
    case = _make_case()

    llm = StubLLMClient([
        _location_payload(),
        _clue_payload(),
        _briefing_payload(),
        {},  # resolution paths LLM returns empty → triggers fallback
    ])

    gen = WorldContentGenerator(llm)
    result = gen.generate(districts=[district], npcs=[npc], cases=[case])

    updated_case = result.case_updates[0]
    assert updated_case.resolution_conditions, "fallback paths must be used when LLM fails"
    fallback = updated_case.resolution_conditions[-1]
    assert fallback["required_credible_count"] == 0
    assert fallback["outcome_status"] == "failed"


def test_generate_sets_hook_npc_id_on_case_update() -> None:
    district = _make_district()
    informant = NPCState(
        id="npc_informant",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        name="Ila Venn",
        role_category="informant",
        district_id="district_old_quarter",
    )
    authority = NPCState(
        id="npc_authority",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        name="Watcher Pell",
        role_category="authority",
        district_id="district_old_quarter",
    )
    case = _make_case()

    location_payload = {
        "locations": [
            {
                "id_slug": "archive_steps",
                "name": "Archive Steps",
                "location_type": "archive",
                "npc_ids": ["npc_informant", "npc_authority"],
                "scene_objects": ["ledger shelf"],
                "is_hidden": False,
            }
        ]
    }
    clue_ids = ["clue_test_001_altered_ledger", "clue_test_001_missing_clerk_note"]

    llm = StubLLMClient([
        location_payload,
        _clue_payload(),
        _briefing_payload(),
        _resolution_paths_payload(clue_ids),
    ])

    gen = WorldContentGenerator(llm)
    result = gen.generate(districts=[district], npcs=[informant, authority], cases=[case])

    updated_case = result.case_updates[0]
    assert updated_case.hook_npc_id == "npc_informant", \
        "informant should be preferred as hook NPC over authority"


def test_pick_hook_npc_prefers_clue_linked_npc_when_roles_are_equal() -> None:
    from lantern_city.generation.world_content import _pick_hook_npc

    witness_a = NPCState(
        id="npc_a", created_at=TURN_ZERO, updated_at=TURN_ZERO,
        name="A", role_category="witness", district_id="district_old_quarter",
    )
    witness_b = NPCState(
        id="npc_b", created_at=TURN_ZERO, updated_at=TURN_ZERO,
        name="B", role_category="witness", district_id="district_old_quarter",
    )
    clue_linked_to_b = ClueState(
        id="clue_x", created_at=TURN_ZERO, updated_at=TURN_ZERO,
        source_type="testimony", source_id="location_x",
        clue_text="B saw something.", reliability="uncertain",
        related_npc_ids=["npc_b"],
        related_case_ids=["case_test_001"],
        related_district_ids=["district_old_quarter"],
    )
    npc_location_map = {"npc_a": "location_x", "npc_b": "location_x"}

    result = _pick_hook_npc([witness_a, witness_b], [clue_linked_to_b], npc_location_map)
    assert result is not None
    assert result.id == "npc_b", "NPC linked to more clues should be preferred when roles are equal"


def test_resolution_paths_clamp_unknown_clue_ids() -> None:
    district = _make_district()
    npc = _make_npc("npc_ila_venn")
    case = _make_case()

    bad_paths = {
        "resolution_paths": [
            {
                "priority": 1,
                "path_id": "clean_exposure",
                "label": "Clean Exposure",
                "outcome_status": "solved",
                "required_clue_ids": ["clue_does_not_exist"],  # invalid ID
                "required_credible_count": 1,
                "summary_text": "Case resolved.",
                "fallout_text": "City shaken.",
            },
            {
                "priority": 2,
                "path_id": "burial",
                "label": "Burial",
                "outcome_status": "failed",
                "required_clue_ids": [],
                "required_credible_count": 0,
                "summary_text": "Evidence insufficient.",
                "fallout_text": "Pressure rises.",
            },
        ]
    }

    llm = StubLLMClient([
        _location_payload(),
        _clue_payload(),
        _briefing_payload(),
        bad_paths,
    ])

    gen = WorldContentGenerator(llm)
    result = gen.generate(districts=[district], npcs=[npc], cases=[case])

    updated_case = result.case_updates[0]
    best_path = next(p for p in updated_case.resolution_conditions if p["priority"] == 1)
    assert "clue_does_not_exist" not in best_path["required_clue_ids"], \
        "unknown clue IDs must be stripped from required_clue_ids"
