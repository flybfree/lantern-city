import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from lantern_city.models import (
    ActiveWorkingSet,
    CaseState,
    CitySeed,
    CityState,
    ClueState,
    DistrictState,
    FactionState,
    GeneratedOutput,
    GenerationJob,
    JSONObject,
    LanternState,
    LocationState,
    NPCState,
    PlayerProgressState,
    PlayerRequest,
    PlayerResponse,
    SceneState,
)

RUNTIME_DEFAULTS = {
    "created_at": "turn_0",
    "updated_at": "turn_0",
}

MODEL_CASES = [
    pytest.param(
        CitySeed,
        {
            "id": "cityseed_001",
            "city_premise": "A rain-soaked port city where lanterns stabilize memory.",
            "dominant_mood": ["noir", "wet"],
            "district_ids": ["district_old_quarter"],
            "faction_ids": ["faction_memory_keepers"],
            "starting_cases": ["case_missing_clerk"],
            "initial_missingness_pressure": 0.35,
            "initial_lantern_profile": {"district_old_quarter": "dim"},
            "key_npc_ids": ["npc_shrine_keeper"],
        },
        id="CitySeed",
    ),
    pytest.param(
        CityState,
        {
            "id": "city_001",
            "updated_at": "turn_1",
            "city_seed_id": "cityseed_001",
            "time_index": 1,
            "global_tension": 0.2,
            "civic_trust": 0.6,
            "missingness_pressure": 0.35,
            "active_case_ids": ["case_missing_clerk"],
            "district_ids": ["district_old_quarter"],
            "faction_ids": ["faction_memory_keepers"],
            "player_presence_level": 0.1,
            "summary_cache": {"short": "The city feels tense."},
        },
        id="CityState",
    ),
    pytest.param(
        DistrictState,
        {
            "id": "district_old_quarter",
            "updated_at": "turn_1",
            "name": "Old Quarter",
            "tone": "ancient, damp, memory-heavy",
            "stability": 0.47,
            "lantern_condition": "dim",
            "governing_power": "faction_memory_keepers",
            "active_problems": ["missing_records"],
            "visible_locations": ["location_archive_steps"],
            "hidden_locations": ["location_subarchive"],
            "relevant_npc_ids": ["npc_shrine_keeper"],
            "rumor_pool": ["Someone edited a family from the ledger."],
            "current_access_level": "restricted",
            "summary_cache": {"short": "The district feels stale and uncertain."},
        },
        id="DistrictState",
    ),
    pytest.param(
        LocationState,
        {
            "id": "location_archive_steps",
            "updated_at": "turn_1",
            "district_id": "district_old_quarter",
            "name": "Archive Steps",
            "location_type": "public_record_site",
            "access_state": "restricted",
            "known_npc_ids": ["npc_archive_clerk"],
            "hidden_feature_ids": ["feature_false_wall"],
            "clue_ids": ["clue_missing_family_entry"],
            "lantern_effects": {"memory_stability": 0.38},
            "description_cache": {"short": "Stone steps leading to the archive."},
        },
        id="LocationState",
    ),
    pytest.param(
        NPCState,
        {
            "id": "npc_shrine_keeper",
            "updated_at": "turn_1",
            "name": "Ila Venn",
            "role_category": "informant",
            "district_id": "district_old_quarter",
            "location_id": "location_shrine_lane",
            "public_identity": "shrine keeper",
            "hidden_objective": "protect a ritual alteration from discovery",
            "current_objective": "redirect the player toward the archive clerk",
            "trust_in_player": 0.56,
            "fear": 0.21,
            "suspicion": 0.33,
            "loyalty": "faction_shrine_circle",
            "known_clue_ids": ["clue_missing_family_entry"],
            "known_promises": ["promise_guidance_to_archive"],
            "relationship_flags": ["hesitant", "useful"],
            "memory_log": [{"turn": 1, "event": "Spoke to the player."}],
            "relevance_rating": 0.74,
        },
        id="NPCState",
    ),
    pytest.param(
        FactionState,
        {
            "id": "faction_memory_keepers",
            "updated_at": "turn_1",
            "name": "Memory Keepers",
            "public_goal": "preserve records and continuity",
            "hidden_goal": "control what the city is allowed to remember",
            "influence_by_district": {"district_old_quarter": 0.78},
            "tension_with_other_factions": {"faction_council_lights": 0.58},
            "attitude_toward_player": "wary",
            "known_assets": ["archives"],
            "known_losses": ["ledger_sabotage"],
            "active_plans": ["stabilize old records"],
            "summary_cache": {"short": "They want control over continuity."},
        },
        id="FactionState",
    ),
    pytest.param(
        LanternState,
        {
            "id": "lantern_old_quarter_01",
            "updated_at": "turn_1",
            "scope_type": "district",
            "scope_id": "district_old_quarter",
            "owner_faction": "faction_council_lights",
            "maintainer_group": "faction_shrine_circle",
            "condition_state": "dim",
            "reach_scope_notes": "Strongest within two blocks of the archive.",
            "social_effects": ["hesitation"],
            "memory_effects": ["inconsistent testimony"],
            "access_effects": ["restricted movement after dark"],
            "anomaly_flags": ["possible_tampering"],
        },
        id="LanternState",
    ),
    pytest.param(
        CaseState,
        {
            "id": "case_missing_clerk",
            "updated_at": "turn_1",
            "title": "The Missing Clerk",
            "case_type": "mystery",
            "status": "active",
            "involved_district_ids": ["district_old_quarter"],
            "involved_npc_ids": ["npc_shrine_keeper"],
            "involved_faction_ids": ["faction_memory_keepers"],
            "known_clue_ids": ["clue_missing_family_entry"],
            "open_questions": ["Who removed the clerk from the records?"],
            "objective_summary": "Determine why the clerk and associated records have vanished.",
        },
        id="CaseState",
    ),
    pytest.param(
        SceneState,
        {
            "id": "scene_014",
            "created_at": "turn_1",
            "updated_at": "turn_1",
            "case_id": "case_missing_clerk",
            "scene_type": "conversation",
            "location_id": "location_archive_steps",
            "participating_npc_ids": ["npc_shrine_keeper"],
            "immediate_goal": "Learn whether the lantern outage is connected to the missing clerk.",
            "current_prompt_state": "awaiting_player_question",
            "scene_clue_ids": ["clue_missing_family_entry"],
            "scene_tension": 0.42,
        },
        id="SceneState",
    ),
    pytest.param(
        ClueState,
        {
            "id": "clue_missing_family_entry",
            "created_at": "turn_1",
            "updated_at": "turn_1",
            "source_type": "document",
            "source_id": "archive_registry_page_11",
            "clue_text": "A family entry appears and disappears across different ledger copies.",
            "reliability": "contradicted",
            "tags": ["records", "memory"],
            "related_npc_ids": ["npc_shrine_keeper"],
            "related_case_ids": ["case_missing_clerk"],
            "related_district_ids": ["district_old_quarter"],
            "status": "new",
        },
        id="ClueState",
    ),
    pytest.param(
        PlayerProgressState,
        {
            "id": "player_progress_001",
            "updated_at": "turn_1",
            "lantern_understanding": {"score": 32, "tier": "Informed"},
            "access": {"score": 21, "tier": "Restricted"},
            "reputation": {"score": 18, "tier": "Wary"},
            "leverage": {"score": 26, "tier": "Useful"},
            "city_impact": {"score": 14, "tier": "Local"},
            "clue_mastery": {"score": 41, "tier": "Competent"},
        },
        id="PlayerProgressState",
    ),
    pytest.param(
        PlayerRequest,
        {
            "id": "req_1001",
            "created_at": "turn_1",
            "updated_at": "turn_1",
            "player_id": "player_001",
            "intent": "talk_to_npc",
            "target_id": "npc_shrine_keeper",
            "location_id": "location_archive_steps",
            "case_id": "case_missing_clerk",
            "scene_id": "scene_014",
            "input_text": "Ask about the lantern outage.",
            "context_refs": {
                "district_id": "district_old_quarter",
                "clue_ids": ["clue_missing_family_entry"],
            },
        },
        id="PlayerRequest",
    ),
    pytest.param(
        GenerationJob,
        {
            "id": "genjob_2001",
            "created_at": "turn_1",
            "updated_at": "turn_1",
            "job_kind": "npc_response",
            "priority": "high",
            "status": "queued",
            "input_refs": {"npc_id": "npc_shrine_keeper", "scene_id": "scene_014"},
            "required_outputs": ["dialogue", "clue_update"],
        },
        id="GenerationJob",
    ),
    pytest.param(
        GeneratedOutput,
        {
            "id": "genout_3001",
            "created_at": "turn_1",
            "updated_at": "turn_1",
            "source_job_id": "genjob_2001",
            "output_kind": "npc_response",
            "text": "The shrine keeper lowers their voice.",
            "structured_updates": {"clue_ids_created": ["clue_outage_before_disappearance"]},
        },
        id="GeneratedOutput",
    ),
    pytest.param(
        PlayerResponse,
        {
            "id": "resp_4001",
            "created_at": "turn_1",
            "updated_at": "turn_1",
            "request_id": "req_1001",
            "narrative_text": "The shrine keeper lowers their voice.",
            "state_changes": [{"type": "clue_added", "clue_id": "clue_outage_before_disappearance"}],
            "next_actions": ["Ask about the archive records", "Inspect the lantern"],
        },
        id="PlayerResponse",
    ),
    pytest.param(
        ActiveWorkingSet,
        {
            "id": "active_slice_001",
            "created_at": "turn_1",
            "updated_at": "turn_1",
            "city_id": "city_001",
            "district_id": "district_old_quarter",
            "location_id": "location_archive_steps",
            "case_id": "case_missing_clerk",
            "scene_id": "scene_014",
            "npc_ids": ["npc_shrine_keeper"],
            "clue_ids": ["clue_missing_family_entry"],
            "cached_summaries": {"district": "The Old Quarter feels stale and uncertain."},
        },
        id="ActiveWorkingSet",
    ),
]


@pytest.mark.parametrize(("model_cls", "payload"), MODEL_CASES)
def test_models_accept_json_friendly_payloads(model_cls: type, payload: dict[str, object]) -> None:
    model = model_cls(**(RUNTIME_DEFAULTS | payload))

    dumped = model.model_dump(mode="json")

    assert dumped["id"] == payload["id"]
    assert dumped["type"] == model_cls.__name__
    assert dumped["version"] == 1
    assert dumped["created_at"]
    assert dumped["updated_at"]
    json.dumps(dumped)


@pytest.mark.parametrize(
    ("model_cls", "payload", "field_name"),
    [
        pytest.param(
            CityState,
            {
                "id": "city_001",
                "created_at": "turn_0",
                "updated_at": "turn_0",
                "city_seed_id": "cityseed_001",
                "time_index": "1",
            },
            "time_index",
            id="int-field",
        ),
        pytest.param(
            CityState,
            {
                "id": "city_001",
                "created_at": "turn_0",
                "updated_at": "turn_0",
                "city_seed_id": "cityseed_001",
                "global_tension": "0.2",
            },
            "global_tension",
            id="float-field",
        ),
        pytest.param(
            NPCState,
            {
                "id": "npc_001",
                "created_at": "turn_0",
                "updated_at": "turn_0",
                "name": "Ila Venn",
                "role_category": "informant",
                "trust_in_player": "0.56",
            },
            "trust_in_player",
            id="numeric-state-field",
        ),
    ],
)
def test_models_reject_coercive_scalar_validation(
    model_cls: type,
    payload: dict[str, object],
    field_name: str,
) -> None:
    with pytest.raises(ValidationError, match=field_name):
        model_cls(**payload)


@pytest.mark.parametrize(
    ("model_cls", "payload", "field_name"),
    [
        pytest.param(
            NPCState,
            {
                "id": "npc_001",
                "created_at": "turn_0",
                "updated_at": "turn_0",
                "name": "Ila Venn",
                "role_category": "informant",
                "memory_log": [{"turn": 1, "event": datetime.now()}],
            },
            "memory_log",
            id="NPCState.memory_log",
        ),
        pytest.param(
            PlayerRequest,
            {
                "id": "req_001",
                "created_at": "turn_0",
                "updated_at": "turn_0",
                "player_id": "player_001",
                "intent": "inspect",
                "context_refs": {"seen_at": datetime.now()},
            },
            "context_refs",
            id="PlayerRequest.context_refs",
        ),
        pytest.param(
            GenerationJob,
            {
                "id": "job_001",
                "created_at": "turn_0",
                "updated_at": "turn_0",
                "job_kind": "npc_response",
                "input_refs": {"seen_at": datetime.now()},
            },
            "input_refs",
            id="GenerationJob.input_refs",
        ),
        pytest.param(
            GeneratedOutput,
            {
                "id": "out_001",
                "created_at": "turn_0",
                "updated_at": "turn_0",
                "source_job_id": "job_001",
                "output_kind": "npc_response",
                "structured_updates": {"seen_at": datetime.now()},
            },
            "structured_updates",
            id="GeneratedOutput.structured_updates",
        ),
        pytest.param(
            PlayerResponse,
            {
                "id": "resp_001",
                "created_at": "turn_0",
                "updated_at": "turn_0",
                "request_id": "req_001",
                "state_changes": [{"type": "noted", "seen_at": datetime.now()}],
            },
            "state_changes",
            id="PlayerResponse.state_changes",
        ),
    ],
)
def test_json_typed_fields_reject_non_json_serializable_values(
    model_cls: type,
    payload: dict[str, object],
    field_name: str,
) -> None:
    with pytest.raises(ValidationError, match=field_name):
        model_cls(**payload)


def test_mutable_defaults_are_not_shared_between_instances() -> None:
    first = CityState(
        id="city_001",
        created_at="turn_0",
        updated_at="turn_0",
        city_seed_id="cityseed_001",
    )
    second = CityState(
        id="city_002",
        created_at="turn_0",
        updated_at="turn_0",
        city_seed_id="cityseed_002",
    )

    first.active_case_ids.append("case_missing_clerk")
    first.summary_cache["short"] = "Changed"

    assert second.active_case_ids == []
    assert second.summary_cache == {}


def test_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="impossible_field"):
        CitySeed(
            id="cityseed_001",
            created_at="turn_0",
            updated_at="turn_0",
            city_premise="Premise",
            impossible_field=True,
        )


def test_json_object_public_type_alias_accepts_nested_json_values() -> None:
    payload: JSONObject = {
        "label": "old quarter",
        "scores": [1, 2, 3],
        "flags": {"dim": True, "missing": None},
    }

    request = PlayerRequest(
        id="req_002",
        created_at="turn_0",
        updated_at="turn_0",
        player_id="player_001",
        intent="inspect",
        context_refs=payload,
    )

    assert request.context_refs == payload
