from __future__ import annotations

from lantern_city.active_slice import ActiveSlice
from lantern_city.case_bootstrap import bootstrap_generated_case
from datetime import UTC, datetime, timedelta

from lantern_city.app import LanternCityApp, _case_runtime_mode, _load_default_seed
from lantern_city.cases import transition_case
from lantern_city.engine import EngineOutcome
from lantern_city.generation.case_generation import (
    CaseGenerationResult,
    GeneratedClueSpec,
    GeneratedNPCSpec,
    GeneratedResolutionPath,
)
from lantern_city.llm_client import OpenAICompatibleConfig
from lantern_city.models import CaseState, ClueState
from lantern_city.response import compose_response
from lantern_city.seed_schema import validate_city_seed


def test_talk_to_npc_surfaces_pre_case_clue_as_new_lead(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"
    app = LanternCityApp(database_path)
    app.start_new_game()
    app.enter_district("district_old_quarter")

    city = app._require_city()
    working_set = app._load_position()
    district = app._district("district_old_quarter")
    npc = app._npc("npc_shrine_keeper")
    clue = app.store.load_object("ClueState", "clue_missing_maintenance_line")

    assert working_set is not None
    assert district is not None
    assert npc is not None
    assert clue is not None

    latent_hint_clue = clue.model_copy(update={"related_case_ids": ["case_latent_hint"]})

    monkeypatch.setattr(LanternCityApp, "_peek_npc_case_hook", lambda self, npc_id: (None, None))

    def fake_handle_player_request(*args, **kwargs) -> EngineOutcome:
        return EngineOutcome(
            intent="talk_to_npc",
            active_slice=ActiveSlice(
                city=city,
                working_set=working_set,
                district=district,
                location=None,
                scene=None,
                npcs=[npc],
                clues=[latent_hint_clue],
                case=None,
            ),
            response=compose_response(
                narrative_text="Ila Venn lowers her voice and points out a detail that should not be easy to explain.",
                state_changes=["Relationship state: guarded but engaged."],
                learned=["Notable clue: Maintenance records were altered after the outage."],
                visible_npcs=[npc.name],
                case_relevance=[
                    "New lead: This clue feels significant, even though you do not yet know what case it belongs to.",
                    "Clue reliability: credible",
                    "Lantern condition: dim",
                ],
                next_actions=["Ask a narrower question"],
            ),
            changed_objects=[],
        )

    monkeypatch.setattr("lantern_city.app.handle_player_request", fake_handle_player_request)

    output = app.talk_to_npc("npc_shrine_keeper", "Ask what seems wrong here.")

    assert "[New lead]" in output
    assert "How the exchange shifted:" in output
    assert "Relationship state: guarded but engaged." in output
    assert "What came out of it:" in output
    assert "Notable clue: Maintenance records were altered after the outage." in output
    assert "What to press next:" in output


def test_inspect_location_surfaces_pre_case_clue_as_new_lead(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"
    app = LanternCityApp(database_path)
    app.start_new_game()
    app.enter_district("district_old_quarter")

    city = app._require_city()
    working_set = app._load_position()
    district = app._district("district_old_quarter")
    location = app.store.load_object("LocationState", "location_archive_steps")
    clue = app.store.load_object("ClueState", "clue_missing_maintenance_line")

    assert working_set is not None
    assert district is not None
    assert location is not None
    assert clue is not None

    latent_hint_clue = clue.model_copy(
        update={"related_case_ids": ["case_latent_hint"], "related_npc_ids": []}
    )

    def fake_handle_player_request(*args, **kwargs) -> EngineOutcome:
        return EngineOutcome(
            intent="inspect_location",
            active_slice=ActiveSlice(
                city=city,
                working_set=working_set,
                district=district,
                location=location,
                scene=None,
                npcs=[],
                clues=[latent_hint_clue],
                case=None,
            ),
            response=compose_response(
                narrative_text="The marks on the archive steps line up too neatly to be wear.",
                state_changes=["Inspection read: a concrete physical sign worth following."],
                learned=["Notable clue: Someone maintained this route after it should have gone dark."],
                notable_objects=["Fresh scoring in the stone"],
                case_relevance=[
                    "New lead: This clue feels significant, even though you do not yet know what case it belongs to.",
                    "Clue reliability: credible",
                    "Lantern condition: dim",
                ],
                next_actions=["Review known clues"],
            ),
            changed_objects=[],
        )

    monkeypatch.setattr("lantern_city.app.handle_player_request", fake_handle_player_request)

    output = app.inspect_location("location_archive_steps")

    assert "[Clue found:" in output
    assert "[New lead]" in output
    assert "How the scene reads:" in output
    assert "Inspection read: a concrete physical sign worth following." in output
    assert "What the scene gives you:" in output
    assert "Someone maintained this route after it should have gone dark." in output
    assert "What to check next:" in output


def test_start_new_game_reports_successful_model_check(tmp_path, monkeypatch) -> None:
    class _PassingProbeClient:
        def __init__(self, config) -> None:
            self.config = config

        def generate_json(self, **kwargs):
            return {
                "task_type": "npc_response",
                "request_id": "probe_npc_response",
                "summary_text": "The witness answers carefully but provides a usable route.",
                "structured_updates": {
                    "dialogue_act": "answer_with_hint",
                    "npc_stance": "guarded but cooperative",
                    "relationship_shift": {
                        "trust_delta": 0.05,
                        "suspicion_delta": 0.0,
                        "fear_delta": 0.0,
                        "tag": "measured_cooperation",
                    },
                    "clue_effects": [],
                    "access_effects": [],
                    "redirect_targets": [],
                },
                "cacheable_text": {
                    "npc_line": "The route is still usable, but only if you move before the ward shutters close.",
                    "follow_up_suggestions": ["Ask who still watches the route."],
                    "exit_line_if_needed": "That is all I can risk saying here.",
                },
                "confidence": 0.82,
                "warnings": [],
            }

        def close(self) -> None:
            return None

    monkeypatch.setattr("lantern_city.app.OpenAICompatibleLLMClient", _PassingProbeClient)
    monkeypatch.setattr(
        LanternCityApp,
        "_generate_city_seed",
        lambda self, concept=None, on_progress=None: validate_city_seed(_load_default_seed()),
    )
    monkeypatch.setattr(
        LanternCityApp,
        "_generate_world_content",
        lambda self, on_progress=None: self._seed_authored_scene_objects(),
    )
    monkeypatch.setattr(LanternCityApp, "_generate_latent_cases", lambda self, count=2: None)

    app = LanternCityApp(
        tmp_path / "lantern-city.sqlite3",
        llm_config=OpenAICompatibleConfig(base_url="http://localhost:1234/v1", model="test-model"),
    )

    output = app.start_new_game()

    assert "Lantern City ready:" in output
    assert "Startup mode: generated_runtime" in output
    assert "Model check: pass" in output


def test_start_new_game_reports_warning_when_model_probe_fails(tmp_path, monkeypatch) -> None:
    class _FailingProbeClient:
        def __init__(self, config) -> None:
            self.config = config

        def generate_json(self, **kwargs):
            raise RuntimeError("bad schema output")

        def close(self) -> None:
            return None

    monkeypatch.setattr("lantern_city.app.OpenAICompatibleLLMClient", _FailingProbeClient)
    monkeypatch.setattr(
        LanternCityApp,
        "_generate_city_seed",
        lambda self, concept=None, on_progress=None: validate_city_seed(_load_default_seed()),
    )
    monkeypatch.setattr(
        LanternCityApp,
        "_generate_world_content",
        lambda self, on_progress=None: self._seed_authored_scene_objects(),
    )
    monkeypatch.setattr(LanternCityApp, "_generate_latent_cases", lambda self, count=2: None)

    app = LanternCityApp(
        tmp_path / "lantern-city.sqlite3",
        llm_config=OpenAICompatibleConfig(base_url="http://localhost:1234/v1", model="test-model"),
    )

    output = app.start_new_game()

    assert "Lantern City ready:" in output
    assert "Startup mode: generated_runtime" in output
    assert "Model check: warning" in output


def test_meaningful_commands_advance_city_time_index(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")

    app.start_new_game()
    assert app.get_state_snapshot()["time_index"] == 0

    app.enter_district("district_old_quarter")
    assert app.get_state_snapshot()["time_index"] == 1

    app.talk_to_npc("npc_shrine_keeper", "Ask who last saw the missing clerk.")
    assert app.get_state_snapshot()["time_index"] == 2

    app.inspect_location("location_shrine_lane")
    assert app.get_state_snapshot()["time_index"] == 3


def test_generated_runtime_applies_idle_delay_catch_up_turns(tmp_path, monkeypatch) -> None:
    start_time = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    times = iter([start_time, start_time + timedelta(minutes=12)])

    monkeypatch.setattr(LanternCityApp, "_now", lambda self: next(times))
    monkeypatch.setattr(
        LanternCityApp,
        "_probe_llm_quality",
        lambda self: "Model check: pass — startup probe validated NPC response quality in 0.1s.",
    )
    monkeypatch.setattr(
        LanternCityApp,
        "_generate_city_seed",
        lambda self, concept=None, on_progress=None: validate_city_seed(_load_default_seed()),
    )
    monkeypatch.setattr(
        LanternCityApp,
        "_generate_world_content",
        lambda self, on_progress=None: self._seed_authored_scene_objects(),
    )
    monkeypatch.setattr(LanternCityApp, "_generate_latent_cases", lambda self, count=2: None)

    app = LanternCityApp(
        tmp_path / "lantern-city.sqlite3",
        llm_config=OpenAICompatibleConfig(base_url="http://localhost:1234/v1", model="test-model"),
        startup_mode="generated_runtime",
    )

    app.start_new_game()
    app.enter_district("district_old_quarter")
    output = app.talk_to_npc("npc_shrine_keeper", "Ask what changed after the outage.")

    assert "[Time passes: 2 extra turn(s)]" in output
    assert app.get_state_snapshot()["time_index"] == 4


def test_mvp_baseline_ignores_idle_delay_catch_up(tmp_path, monkeypatch) -> None:
    start_time = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    times = iter([start_time, start_time + timedelta(minutes=12)])

    monkeypatch.setattr(LanternCityApp, "_now", lambda self: next(times))

    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")

    app.start_new_game()
    app.enter_district("district_old_quarter")
    output = app.talk_to_npc("npc_shrine_keeper", "Ask what changed after the outage.")

    assert "[Time passes:" not in output
    assert app.get_state_snapshot()["time_index"] == 2


def test_case_board_includes_actionable_recovery_section(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")
    app._acquire_clues(
        [
            "clue_missing_clerk_ledgers",
            "clue_family_record_discrepancy",
            "clue_missing_maintenance_line",
        ]
    )

    output = app.case_board()

    assert "=== Case Board: Missing Clerk ===" in output
    assert "Best evidence:" in output
    assert "Role: supports current case" in output
    assert "Role: contradiction to explain" in output
    assert "Role: paper trail to test" in output
    assert "Why it matters:" in output
    assert "Follow up:" in output
    assert "What this suggests:" in output
    assert "Do next:" in output
    assert "Use 'leads' to rank the strongest unresolved thread." in output


def test_advance_case_warns_before_terminal_failure(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    city = app._require_city()
    app.store.save_object(
        CaseState(
            id="case_gen_failure_warning_001",
            created_at="turn_0",
            updated_at="turn_0",
            title="Quiet Ledger",
            case_type="records tampering",
            status="active",
            involved_district_ids=["district_old_quarter"],
            objective_summary="Prove the altered record trail before it closes.",
        )
    )
    app.store.save_object(
        city.model_copy(update={"active_case_ids": [*city.active_case_ids, "case_gen_failure_warning_001"]})
    )
    app._introduce_case("case_gen_failure_warning_001")

    output = app.advance_case("case_gen_failure_warning_001")
    case = app.store.load_object("CaseState", "case_gen_failure_warning_001")

    assert case is not None
    assert case.status in {"active", "escalated"}
    assert case.pressure_level == "urgent"
    assert "failure_warning_issued" in case.offscreen_risk_flags
    assert "Resolution attempt: not enough evidence yet" in output
    assert "This case is not failed yet" in output
    assert "Final warning:" in output


def test_advance_case_fails_after_warning_is_issued(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    city = app._require_city()
    app.store.save_object(
        CaseState(
            id="case_gen_failure_warning_002",
            created_at="turn_0",
            updated_at="turn_0",
            title="Borrowed Seal",
            case_type="records tampering",
            status="active",
            involved_district_ids=["district_old_quarter"],
            objective_summary="Catch the forged certification trail before it settles.",
        )
    )
    app.store.save_object(
        city.model_copy(update={"active_case_ids": [*city.active_case_ids, "case_gen_failure_warning_002"]})
    )
    app._introduce_case("case_gen_failure_warning_002")

    app.advance_case("case_gen_failure_warning_002")
    output = app.advance_case("case_gen_failure_warning_002")
    case = app.store.load_object("CaseState", "case_gen_failure_warning_002")

    assert case is not None
    assert case.status == "failed"
    assert "Case status: failed" in output
    assert "This case is now closed. You cannot keep solving it directly" in output


def test_status_and_board_surface_failure_risk_warning(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")
    case = app.store.load_object("CaseState", "case_missing_clerk")
    assert case is not None
    app.store.save_object(
        case.model_copy(
            update={
                "status": "escalated",
                "pressure_level": "urgent",
                "active_resolution_window": "narrowing",
                "offscreen_risk_flags": [*case.offscreen_risk_flags, "failure_warning_issued"],
            }
        )
    )

    status_output = app.status()
    board_output = app.case_board("case_missing_clerk")

    expected = "Failure risk: One more unsupported close attempt will bury the case."
    assert expected in status_output
    assert expected in board_output


def test_journal_includes_stuck_recovery_actions(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")
    app._acquire_clues(["clue_missing_clerk_ledgers"])

    output = app.journal()

    assert "=== Journal ===" in output
    assert "role: supports current case" in output
    assert "Do next:" in output
    assert "  - board case_missing_clerk" in output
    assert "  - leads" in output
    assert "  - compare <clue_a> <clue_b>" not in output


def test_strongest_leads_includes_recovery_footer(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")
    app._acquire_clues(["clue_missing_clerk_ledgers"])

    output = app.strongest_leads()

    assert "=== Strongest Leads ===" in output
    assert "Read:" in output
    assert "What this suggests:" in output
    assert "Do next:" in output
    assert "  - board case_missing_clerk" in output
    assert "  - leads" in output


def test_status_summarizes_clue_picture(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")
    app._acquire_clues(
        [
            "clue_missing_clerk_ledgers",
            "clue_family_record_discrepancy",
            "clue_missing_maintenance_line",
        ]
    )

    output = app.status()

    assert "=== Investigator Status ===" in output
    assert "Clue picture:" in output
    assert "support the case theory" in output


def test_status_board_and_journal_surface_institutional_pressure_reads(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    city = app._require_city()
    app.store.save_object(city.model_copy(update={"active_case_ids": ["case_gen_pressure_read_001"]}))
    case = CaseState(
        id="case_gen_pressure_read_001",
        created_at="turn_0",
        updated_at="turn_0",
        title="Ledger Shadow",
        case_type="records tampering",
        status="active",
        involved_district_ids=["district_old_quarter"],
        involved_faction_ids=["faction_memory_keepers"],
        known_clue_ids=["clue_records_pressure_001"],
        pressure_level="rising",
        offscreen_risk_flags=["records_drift:faction_memory_keepers", "coverup:faction_memory_keepers"],
        district_effects=["coverup:faction_memory_keepers"],
        objective_summary="Track a falsified corrections trail.",
    )
    app.store.save_object(case)
    app._introduce_case(case.id)

    status_output = app.status()
    board_output = app.case_board(case.id)
    journal_output = app.journal()

    expected = "Memory Keepers is degrading paper certainty and smothering the record trail"
    assert f"Institutional pressure: {expected}" in status_output
    assert f"Institutional pressure: {expected}" in board_output
    assert f"institutional pressure: {expected}" in journal_output


def test_records_pressure_changes_recovery_guidance_across_surfaces(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")
    case = app.store.load_object("CaseState", "case_missing_clerk")
    assert case is not None
    app.store.save_object(
        case.model_copy(
            update={
                "involved_faction_ids": ["faction_memory_keepers"],
                "offscreen_risk_flags": [
                    *case.offscreen_risk_flags,
                    "records_drift:faction_memory_keepers",
                    "coverup:faction_memory_keepers",
                ],
                "district_effects": [
                    *case.district_effects,
                    "coverup:faction_memory_keepers",
                ],
            }
        )
    )

    status_output = app.status()
    board_output = app.case_board("case_missing_clerk")
    leads_output = app.strongest_leads()

    expected = "Use 'matters' in Old Quarter to press on copies, ledgers, and corroborating records before they shift again."
    assert expected in status_output
    assert expected in board_output
    assert expected in leads_output
    assert "Use 'compare <clue_a> <clue_b>' to catch record inconsistencies before they settle into the official version." in status_output


def test_civic_pressure_changes_recovery_guidance_across_surfaces(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")
    case = app.store.load_object("CaseState", "case_missing_clerk")
    assert case is not None
    app.store.save_object(
        case.model_copy(
            update={
                "involved_faction_ids": ["faction_council_lights"],
                "involved_npc_ids": ["npc_archive_clerk"],
                "offscreen_risk_flags": [
                    *case.offscreen_risk_flags,
                    "isolation:faction_council_lights",
                ],
            }
        )
    )

    status_output = app.status()
    board_output = app.case_board("case_missing_clerk")
    journal_output = app.journal()

    assert "Talk to Sered Marr before procedure hardens the witness picture any further." in status_output
    assert "Talk to Sered Marr before procedure hardens the witness picture any further." in board_output
    assert "Use 'matters' in Old Quarter to see which people and places are still reachable before access closes." in journal_output


def test_status_and_journal_surface_social_pressure(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app.go("location_shrine_lane")
    npc = app._npc("npc_shrine_keeper")
    assert npc is not None
    app.store.save_object(
        npc.model_copy(
            update={
                "offscreen_state": "obstructing",
                "memory_log": [
                    *npc.memory_log,
                    {
                        "memory_type": "offscreen_event",
                        "turn": "turn_3",
                        "offscreen_state": "obstructing",
                        "summary_text": "obstructing via location_shrine_lane",
                        "source_actor_id": "world",
                    },
                ],
                "relationships": {
                    **npc.relationships,
                    "player": npc.relationships["player"].model_copy(update={"status": "guarded"}),
                    npc.loyalty: npc.relationships[npc.loyalty].model_copy(update={"status": "aligned"}),
                },
            }
        )
    )

    status_output = app.status()
    journal_output = app.journal()

    assert "Social pressure: Ila Venn is currently obstructing;" in status_output
    assert "toward you: guarded" in status_output
    assert "Recent social pressure:" in journal_output
    assert "Ila Venn: faction_memory_keepers reads as aligned while obstructing." in journal_output


def test_world_turn_output_surfaces_faction_pressure(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()

    output = app.enter_district("district_old_quarter")
    faction = app.store.load_object("FactionState", "faction_memory_keepers")

    assert "Faction pressure:" in output
    assert "Memory Keepers is tightening its posture in district_old_quarter." in output
    assert "Memory Keepers is now guarded toward you." in output
    assert faction is not None
    assert faction.attitude_toward_player == "guarded"


def test_faction_turn_operations_pressure_generated_case_and_targeted_npc(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.store.save_object(
        CaseState(
            id="case_gen_pressure_001",
            created_at="turn_0",
            updated_at="turn_0",
            title="Night Manifest",
            case_type="records tampering",
            status="escalated",
            involved_district_ids=["district_lantern_ward"],
            involved_npc_ids=["npc_watcher_pell"],
            involved_faction_ids=["faction_council_lights"],
            npc_pressure_targets=["npc_watcher_pell"],
            pressure_level="urgent",
            time_since_last_progress=2,
            offscreen_risk_flags=["urgent_window"],
            objective_summary="Work out who is rewriting the ledger trail and why.",
        )
    )
    city = app._require_city()
    app.store.save_object(
        city.model_copy(update={"active_case_ids": [*city.active_case_ids, "case_gen_pressure_001"]})
    )
    app._introduce_case("case_gen_pressure_001")

    output = app.enter_district("district_lantern_ward")
    pressured_case = app.store.load_object("CaseState", "case_gen_pressure_001")
    pressured_npc = app.store.load_object("NPCState", "npc_watcher_pell")
    district = app.store.load_object("DistrictState", "district_lantern_ward")

    assert pressured_case is not None
    assert pressured_npc is not None
    assert district is not None
    assert "Faction pressure:" in output
    assert "Council of Lights is isolating witnesses around Night Manifest." in output
    assert "Council of Lights is leaning on Watcher Pell over Night Manifest." in output
    assert "isolation:faction_council_lights" in pressured_case.offscreen_risk_flags
    assert "isolation:faction_council_lights" in pressured_case.district_effects
    assert pressured_npc.offscreen_state == "obstructing"
    assert pressured_npc.suspicion > 0.0
    assert any(
        isinstance(entry, dict)
        and entry.get("memory_type") == "offscreen_event"
        and "Night Manifest" in str(entry.get("summary_text", ""))
        for entry in pressured_npc.memory_log
    )
    assert "faction_surveillance:faction_council_lights" in district.active_problems
    assert district.current_access_level in {"controlled", "restricted"}


def test_records_faction_drift_degrades_document_clue_over_time(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    city = app._require_city()
    app.store.save_object(city.model_copy(update={"active_case_ids": ["case_gen_records_001"]}))
    app.store.save_object(
        CaseState(
            id="case_gen_records_001",
            created_at="turn_0",
            updated_at="turn_0",
            title="Ledger Shadow",
            case_type="records tampering",
            status="active",
            involved_district_ids=["district_old_quarter"],
            involved_faction_ids=["faction_memory_keepers"],
            known_clue_ids=["clue_records_pressure_001"],
            pressure_level="rising",
            time_since_last_progress=1,
            objective_summary="Track a falsified corrections trail.",
        )
    )
    app.store.save_object(
        ClueState(
            id="clue_records_pressure_001",
            created_at="turn_0",
            updated_at="turn_0",
            source_type="document",
            source_id="location_ledger_room",
            clue_text="A correction ledger was rewritten after dusk.",
            reliability="credible",
            related_case_ids=["case_gen_records_001"],
        )
    )

    notices = app._run_case_pressure_updates(
        updated_at="turn_2",
        progressed_case_ids=set(),
        focus_district_id="district_old_quarter",
    )

    clue = app.store.load_object("ClueState", "clue_records_pressure_001")

    assert clue is not None
    assert clue.reliability == "uncertain"
    assert any("muddying the paper trail" in notice for notice in notices)
    assert any("reliability now uncertain" in notice for notice in notices)


def test_civic_faction_drift_tightens_district_access_over_time(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    city = app._require_city()
    app.store.save_object(city.model_copy(update={"active_case_ids": ["case_gen_civic_001"]}))
    app.store.save_object(
        CaseState(
            id="case_gen_civic_001",
            created_at="turn_0",
            updated_at="turn_0",
            title="Dock Inquiry",
            case_type="procedural obstruction",
            status="active",
            involved_district_ids=["district_the_docks"],
            npc_pressure_targets=["npc_dockmaster"],
            involved_faction_ids=["faction_council_lights"],
            pressure_level="rising",
            time_since_last_progress=1,
            objective_summary="Work out who is constricting access at the docks.",
        )
    )

    notices = app._run_case_pressure_updates(
        updated_at="turn_2",
        progressed_case_ids=set(),
        focus_district_id="district_the_docks",
    )

    district = app.store.load_object("DistrictState", "district_the_docks")
    npc = app.store.load_object("NPCState", "npc_dockmaster")

    assert district is not None
    assert npc is not None
    assert district.current_access_level == "watched"
    assert "civic_pressure:faction_council_lights" in district.active_problems
    assert any("narrowing official access" in notice for notice in notices)
    assert npc.offscreen_state == "obstructing"
    assert npc.suspicion > 0.0
    assert any("more procedural and guarded" in notice for notice in notices)


def test_overview_and_status_surface_faction_posture(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")

    overview_output = app.overview()
    status_output = app.status()

    assert "Faction posture:" in overview_output
    assert "Memory Keepers: guarded toward you, focused on district_old_quarter" in overview_output
    assert "style=records control" in overview_output
    assert "tactic=tightening official scrutiny" in overview_output
    assert "Faction posture:" in status_output
    assert "toward you" in status_output
    assert "focused on district_old_quarter" in status_output
    assert "style=records control" in status_output


def test_what_matters_here_includes_exact_next_commands(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app.go("location_ledger_room")

    output = app.what_matters_here()

    assert "=== What Matters Here: Old Quarter ===" in output
    assert "Do next:" in output
    assert "  - inspect location_ledger_room" in output
    assert "  - talk npc_archive_clerk <question>" in output
    assert "  - leads" in output


def test_compare_clues_includes_recovery_guidance(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._acquire_clues(["clue_missing_clerk_ledgers", "clue_missing_maintenance_line"])
    app._introduce_case("case_missing_clerk")

    output = app.compare_clues("clue_missing_clerk_ledgers", "clue_missing_maintenance_line")

    assert "=== Compare Clues ===" in output
    assert "Do next:" in output
    assert "  - board" in output
    assert "  - talk npc_brin_hesse" in output
    assert "  - matters" in output


def test_clues_surface_support_contradiction_and_follow_up_roles(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")
    app._acquire_clues(
        [
            "clue_missing_clerk_ledgers",
            "clue_family_record_discrepancy",
            "clue_missing_maintenance_line",
        ]
    )

    output = app.clues()

    assert "Role: supports current case" in output
    assert "Role: contradiction to explain" in output
    assert "Role: paper trail to test" in output
    assert "Why it matters:" in output
    assert "Follow up:" in output


def test_generated_case_recovery_surfaces_use_generated_case_id(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")

    city = app._require_city()
    result = CaseGenerationResult(
        request_id="req_case_001",
        title="Borrowed Ledger",
        case_type="records tampering",
        intensity="medium",
        opening_hook="Someone has been copying numbers out of the docks ledger before dawn.",
        objective_summary="Work out who is rewriting the ledger trail and why.",
        involved_district_ids=["district_old_quarter", "district_the_docks"],
        hook_npc_index=0,
        npc_specs=[
            GeneratedNPCSpec(
                name="Mira Sorn",
                role_category="informant",
                district_id="district_old_quarter",
                location_type_hint="records",
                public_identity="Night copyist",
                hidden_objective="Keep a stolen ledger page out of official hands.",
                current_objective="Find out who else has seen the copied figures.",
                trust_in_player=0.4,
                suspicion=0.2,
                fear=0.3,
            )
        ],
        clue_specs=[
            GeneratedClueSpec(
                source_type="document",
                district_id="district_old_quarter",
                location_type_hint="records",
                clue_text="A copied page lists dock transfers that do not match the official ledger.",
                starting_reliability="credible",
                known_by_npc_index=0,
            ),
            GeneratedClueSpec(
                source_type="testimony",
                district_id="district_the_docks",
                location_type_hint="office",
                clue_text="A dock runner swears the copied numbers changed after the lamps were dimmed.",
                starting_reliability="uncertain",
                known_by_npc_index=None,
            ),
            GeneratedClueSpec(
                source_type="physical",
                district_id="district_old_quarter",
                location_type_hint="records",
                clue_text="Ink scoring on a ledger shelf suggests a page was removed in haste.",
                starting_reliability="uncertain",
                known_by_npc_index=None,
            ),
        ],
        resolution_paths=[
            GeneratedResolutionPath(
                path_id="best_path",
                label="Trace the copied ledger",
                outcome_status="solved",
                required_clue_indices=[0, 2],
                required_credible_count=2,
                summary_text="You pin the forged transfer trail to the right hands.",
                fallout_text="The docks go quiet for one watch, then louder than before.",
                priority=1,
            ),
            GeneratedResolutionPath(
                path_id="fallback_path",
                label="Prove the tampering happened",
                outcome_status="partially solved",
                required_clue_indices=[0],
                required_credible_count=1,
                summary_text="You prove the ledger changed, but not who moved it.",
                fallout_text="Someone upstream has time to clean the rest.",
                priority=2,
            ),
        ],
    )
    bootstrap = bootstrap_generated_case(
        result,
        store=app.store,
        city=city,
        case_index=1,
        updated_at="turn_test",
    )
    app.store.save_objects_atomically(
        [
            transition_case(bootstrap.case, "active", updated_at="turn_test_active"),
            *bootstrap.npcs,
            *bootstrap.clues,
            *bootstrap.updated_locations,
            *bootstrap.updated_districts,
            bootstrap.updated_city,
        ]
    )
    app._introduce_case(bootstrap.case.id)
    app._acquire_clues([bootstrap.clues[0].id, bootstrap.clues[1].id])

    journal_output = app.journal()
    leads_output = app.strongest_leads()

    assert "Borrowed Ledger" in journal_output
    assert "  - board case_gen_001" in journal_output
    assert "Borrowed Ledger" in leads_output
    assert "  - board case_gen_001" in leads_output


def test_case_runtime_mode_marks_missing_clerk_as_mvp_baseline(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()

    case = app.store.load_object("CaseState", "case_missing_clerk")

    assert case is not None
    assert _case_runtime_mode(case) == "mvp_baseline"


def test_case_runtime_mode_marks_generated_cases_as_evolved_runtime(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()

    city = app._require_city()
    generated = CaseGenerationResult(
        request_id="req_case_003",
        title="Night Manifest",
        case_type="shipping fraud",
        intensity="medium",
        opening_hook="Someone is rewriting the night manifest before the dock bells ring.",
        objective_summary="Find who is altering the manifest trail.",
        involved_district_ids=["district_old_quarter", "district_the_docks"],
        hook_npc_index=0,
        npc_specs=[
            GeneratedNPCSpec(
                name="Hadrin Voss",
                role_category="informant",
                district_id="district_the_docks",
                location_type_hint="office",
                public_identity="night tally clerk",
                hidden_objective="Keep one shipment off the books.",
                current_objective="Find out who noticed the revised manifest.",
                trust_in_player=0.3,
                suspicion=0.4,
                fear=0.4,
            )
        ],
        clue_specs=[
            GeneratedClueSpec(
                source_type="document",
                district_id="district_the_docks",
                location_type_hint="office",
                clue_text="The night manifest shows a corrected cargo line in fresher ink.",
                starting_reliability="credible",
                known_by_npc_index=0,
            ),
            GeneratedClueSpec(
                source_type="physical",
                district_id="district_old_quarter",
                location_type_hint="records",
                clue_text="A torn wax seal matches the corrected manifest bundle.",
                starting_reliability="uncertain",
                known_by_npc_index=None,
            ),
            GeneratedClueSpec(
                source_type="testimony",
                district_id="district_the_docks",
                location_type_hint="office",
                clue_text="A runner claims the manifest changed after the lamps dimmed.",
                starting_reliability="uncertain",
                known_by_npc_index=None,
            ),
        ],
        resolution_paths=[
            GeneratedResolutionPath(
                path_id="best_path",
                label="Trace the revised manifest",
                outcome_status="solved",
                required_clue_indices=[0, 1],
                required_credible_count=2,
                summary_text="You tie the forged manifest to the right hands.",
                fallout_text="Dock traffic shifts before dawn and everyone notices.",
                priority=1,
            ),
            GeneratedResolutionPath(
                path_id="fallback_path",
                label="Prove the manifest changed",
                outcome_status="partially solved",
                required_clue_indices=[0],
                required_credible_count=1,
                summary_text="You prove the record changed, but not who changed it.",
                fallout_text="The docks close ranks around the missing names.",
                priority=2,
            ),
        ],
    )
    bootstrap = bootstrap_generated_case(
        generated,
        store=app.store,
        city=city,
        case_index=3,
        updated_at="turn_test",
    )

    assert _case_runtime_mode(bootstrap.case) == "evolved_runtime"


def test_start_new_game_can_force_mvp_baseline_even_with_llm_config(tmp_path, monkeypatch) -> None:
    class _PassingProbeClient:
        def __init__(self, config) -> None:
            self.config = config

        def generate_json(self, **kwargs):
            return {
                "task_type": "npc_response",
                "request_id": "probe_npc_response",
                "summary_text": "The witness answers carefully but provides a usable route.",
                "structured_updates": {
                    "dialogue_act": "answer_with_hint",
                    "npc_stance": "guarded but cooperative",
                    "relationship_shift": {
                        "trust_delta": 0.05,
                        "suspicion_delta": 0.0,
                        "fear_delta": 0.0,
                        "tag": "measured_cooperation",
                    },
                    "clue_effects": [],
                    "access_effects": [],
                    "redirect_targets": [],
                },
                "cacheable_text": {
                    "npc_line": "The route is still usable, but only if you move before the ward shutters close.",
                    "follow_up_suggestions": ["Ask who still watches the route."],
                    "exit_line_if_needed": "That is all I can risk saying here.",
                },
                "confidence": 0.82,
                "warnings": [],
            }

        def close(self) -> None:
            return None

    monkeypatch.setattr("lantern_city.app.OpenAICompatibleLLMClient", _PassingProbeClient)

    generate_world_called = False
    generate_cases_called = False

    def _mark_world(self, on_progress=None):
        nonlocal generate_world_called
        generate_world_called = True

    def _mark_cases(self, count=2):
        nonlocal generate_cases_called
        generate_cases_called = True

    monkeypatch.setattr(LanternCityApp, "_generate_world_content", _mark_world)
    monkeypatch.setattr(LanternCityApp, "_generate_latent_cases", _mark_cases)

    app = LanternCityApp(
        tmp_path / "lantern-city.sqlite3",
        llm_config=OpenAICompatibleConfig(base_url="http://localhost:1234/v1", model="test-model"),
        startup_mode="mvp_baseline",
    )

    output = app.start_new_game()

    assert "Active case: The Missing Clerk" in output
    assert "Startup mode: mvp_baseline" in output
    assert "Model check:" not in output
    assert generate_world_called is False
    assert generate_cases_called is False


def test_start_new_game_rejects_generated_runtime_without_llm(tmp_path) -> None:
    app = LanternCityApp(
        tmp_path / "lantern-city.sqlite3",
        startup_mode="generated_runtime",
    )

    try:
        app.start_new_game()
    except ValueError as exc:
        assert "requires llm_config" in str(exc)
    else:
        raise AssertionError("Expected generated runtime startup without llm_config to fail")
