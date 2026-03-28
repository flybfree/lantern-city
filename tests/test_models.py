import json

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
    LanternState,
    LocationState,
    NPCState,
    PlayerProgressState,
    PlayerRequest,
    PlayerResponse,
    SceneState,
)


def test_all_required_models_can_be_instantiated_with_json_friendly_data() -> None:
    city_seed = CitySeed(
        id="cityseed_001",
        created_at="turn_0",
        updated_at="turn_0",
        city_premise="A rain-soaked port city where lanterns stabilize memory.",
        dominant_mood=["noir", "wet"],
        district_ids=["district_old_quarter"],
        faction_ids=["faction_memory_keepers"],
        starting_cases=["case_missing_clerk"],
        initial_missingness_pressure=0.35,
        initial_lantern_profile={"district_old_quarter": "dim"},
        key_npc_ids=["npc_shrine_keeper"],
    )

    city_state = CityState(
        id="city_001",
        created_at="turn_0",
        updated_at="turn_1",
        city_seed_id=city_seed.id,
        time_index=1,
        global_tension=0.2,
        civic_trust=0.6,
        missingness_pressure=0.35,
        active_case_ids=["case_missing_clerk"],
        district_ids=["district_old_quarter"],
        faction_ids=["faction_memory_keepers"],
        player_presence_level=0.1,
        summary_cache={"short": "The city feels tense."},
    )

    district_state = DistrictState(
        id="district_old_quarter",
        created_at="turn_0",
        updated_at="turn_1",
        name="Old Quarter",
        tone="ancient, damp, memory-heavy",
        stability=0.47,
        lantern_condition="dim",
        governing_power="faction_memory_keepers",
        active_problems=["missing_records"],
        visible_locations=["location_archive_steps"],
        hidden_locations=["location_subarchive"],
        relevant_npc_ids=["npc_shrine_keeper"],
        rumor_pool=["Someone edited a family from the ledger."],
        current_access_level="restricted",
        summary_cache={"short": "The district feels stale and uncertain."},
    )

    location_state = LocationState(
        id="location_archive_steps",
        created_at="turn_0",
        updated_at="turn_1",
        district_id=district_state.id,
        name="Archive Steps",
        location_type="public_record_site",
        access_state="restricted",
        known_npc_ids=["npc_archive_clerk"],
        hidden_feature_ids=["feature_false_wall"],
        clue_ids=["clue_missing_family_entry"],
        lantern_effects={"memory_stability": 0.38},
        description_cache={"short": "Stone steps leading to the archive."},
    )

    npc_state = NPCState(
        id="npc_shrine_keeper",
        created_at="turn_0",
        updated_at="turn_1",
        name="Ila Venn",
        role_category="informant",
        district_id=district_state.id,
        location_id="location_shrine_lane",
        public_identity="shrine keeper",
        hidden_objective="protect a ritual alteration from discovery",
        current_objective="redirect the player toward the archive clerk",
        trust_in_player=0.56,
        fear=0.21,
        suspicion=0.33,
        loyalty="faction_shrine_circle",
        known_clue_ids=["clue_missing_family_entry"],
        known_promises=["promise_guidance_to_archive"],
        relationship_flags=["hesitant", "useful"],
        memory_log=[{"turn": 1, "event": "Spoke to the player."}],
        relevance_rating=0.74,
    )

    faction_state = FactionState(
        id="faction_memory_keepers",
        created_at="turn_0",
        updated_at="turn_1",
        name="Memory Keepers",
        public_goal="preserve records and continuity",
        hidden_goal="control what the city is allowed to remember",
        influence_by_district={district_state.id: 0.78},
        tension_with_other_factions={"faction_council_lights": 0.58},
        attitude_toward_player="wary",
        known_assets=["archives"],
        known_losses=["ledger_sabotage"],
        active_plans=["stabilize old records"],
        summary_cache={"short": "They want control over continuity."},
    )

    lantern_state = LanternState(
        id="lantern_old_quarter_01",
        created_at="turn_0",
        updated_at="turn_1",
        scope_type="district",
        scope_id=district_state.id,
        owner_faction="faction_council_lights",
        maintainer_group="faction_shrine_circle",
        condition_state="dim",
        reach_scope_notes="Strongest within two blocks of the archive.",
        social_effects=["hesitation"],
        memory_effects=["inconsistent testimony"],
        access_effects=["restricted movement after dark"],
        anomaly_flags=["possible_tampering"],
    )

    case_state = CaseState(
        id="case_missing_clerk",
        created_at="turn_0",
        updated_at="turn_1",
        title="The Missing Clerk",
        case_type="mystery",
        status="active",
        involved_district_ids=[district_state.id],
        involved_npc_ids=[npc_state.id],
        involved_faction_ids=[faction_state.id],
        known_clue_ids=["clue_missing_family_entry"],
        open_questions=["Who removed the clerk from the records?"],
        objective_summary="Determine why the clerk and associated records have vanished.",
        resolution_summary=None,
        fallout_summary=None,
    )

    scene_state = SceneState(
        id="scene_014",
        created_at="turn_1",
        updated_at="turn_1",
        case_id=case_state.id,
        scene_type="conversation",
        location_id=location_state.id,
        participating_npc_ids=[npc_state.id],
        immediate_goal="Learn whether the lantern outage is connected to the missing clerk.",
        current_prompt_state="awaiting_player_question",
        scene_clue_ids=["clue_missing_family_entry"],
        scene_tension=0.42,
        scene_outcome=None,
    )

    clue_state = ClueState(
        id="clue_missing_family_entry",
        created_at="turn_1",
        updated_at="turn_1",
        source_type="document",
        source_id="archive_registry_page_11",
        clue_text="A family entry appears and disappears across different ledger copies.",
        reliability="contradicted",
        tags=["records", "memory"],
        related_npc_ids=[npc_state.id],
        related_case_ids=[case_state.id],
        related_district_ids=[district_state.id],
        status="new",
    )

    player_progress = PlayerProgressState(
        id="player_progress_001",
        created_at="turn_0",
        updated_at="turn_1",
        lantern_understanding={"score": 32, "tier": "Informed"},
        access={"score": 21, "tier": "Restricted"},
        reputation={"score": 18, "tier": "Wary"},
        leverage={"score": 26, "tier": "Useful"},
        city_impact={"score": 14, "tier": "Local"},
        clue_mastery={"score": 41, "tier": "Competent"},
    )

    player_request = PlayerRequest(
        id="req_1001",
        created_at="turn_1",
        updated_at="turn_1",
        player_id="player_001",
        intent="talk_to_npc",
        target_id=npc_state.id,
        location_id=location_state.id,
        case_id=case_state.id,
        scene_id=scene_state.id,
        input_text="Ask about the lantern outage.",
        context_refs={"district_id": district_state.id, "clue_ids": [clue_state.id]},
    )

    generation_job = GenerationJob(
        id="genjob_2001",
        created_at="turn_1",
        updated_at="turn_1",
        job_kind="npc_response",
        priority="high",
        status="queued",
        input_refs={"npc_id": npc_state.id, "scene_id": scene_state.id},
        required_outputs=["dialogue", "clue_update"],
        cached_output_id=None,
    )

    generated_output = GeneratedOutput(
        id="genout_3001",
        created_at="turn_1",
        updated_at="turn_1",
        source_job_id=generation_job.id,
        output_kind="npc_response",
        text="The shrine keeper lowers their voice.",
        structured_updates={"clue_ids_created": ["clue_outage_before_disappearance"]},
    )

    player_response = PlayerResponse(
        id="resp_4001",
        created_at="turn_1",
        updated_at="turn_1",
        request_id=player_request.id,
        narrative_text=generated_output.text,
        state_changes=[{"type": "clue_added", "clue_id": "clue_outage_before_disappearance"}],
        next_actions=["Ask about the archive records", "Inspect the lantern"],
    )

    working_set = ActiveWorkingSet(
        id="active_slice_001",
        created_at="turn_1",
        updated_at="turn_1",
        city_id=city_state.id,
        district_id=district_state.id,
        location_id=location_state.id,
        case_id=case_state.id,
        scene_id=scene_state.id,
        npc_ids=[npc_state.id],
        clue_ids=[clue_state.id],
        cached_summaries={"district": "The Old Quarter feels stale and uncertain."},
    )

    models = [
        city_seed,
        city_state,
        district_state,
        location_state,
        npc_state,
        faction_state,
        lantern_state,
        case_state,
        scene_state,
        clue_state,
        player_progress,
        player_request,
        generation_job,
        generated_output,
        player_response,
        working_set,
    ]

    assert [model.type for model in models] == [
        "CitySeed",
        "CityState",
        "DistrictState",
        "LocationState",
        "NPCState",
        "FactionState",
        "LanternState",
        "CaseState",
        "SceneState",
        "ClueState",
        "PlayerProgressState",
        "PlayerRequest",
        "GenerationJob",
        "GeneratedOutput",
        "PlayerResponse",
        "ActiveWorkingSet",
    ]

    for model in models:
        dumped = model.model_dump(mode="json")
        assert dumped["id"]
        assert dumped["type"]
        assert dumped["version"] == 1
        assert dumped["created_at"]
        assert dumped["updated_at"]
        json.dumps(dumped)


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
    try:
        CitySeed(
            id="cityseed_001",
            created_at="turn_0",
            updated_at="turn_0",
            city_premise="Premise",
            impossible_field=True,
        )
    except ValidationError as exc:
        assert "impossible_field" in str(exc)
    else:
        raise AssertionError("Expected validation error for unknown field")
