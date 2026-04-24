from __future__ import annotations

from lantern_city.active_slice import ActiveSlice
from lantern_city.case_bootstrap import bootstrap_generated_case
from lantern_city.app import LanternCityApp, _load_default_seed
from lantern_city.cases import transition_case
from lantern_city.engine import EngineOutcome
from lantern_city.generation.case_generation import (
    CaseGenerationResult,
    GeneratedClueSpec,
    GeneratedNPCSpec,
    GeneratedResolutionPath,
)
from lantern_city.llm_client import OpenAICompatibleConfig
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
    assert "What you learned:" in output
    assert "Notable clue: Maintenance records were altered after the outage." in output


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
    assert "Someone maintained this route after it should have gone dark." in output


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
    monkeypatch.setattr(LanternCityApp, "_generate_world_content", lambda self, on_progress=None: None)
    monkeypatch.setattr(LanternCityApp, "_generate_latent_cases", lambda self, count=2: None)

    app = LanternCityApp(
        tmp_path / "lantern-city.sqlite3",
        llm_config=OpenAICompatibleConfig(base_url="http://localhost:1234/v1", model="test-model"),
    )

    output = app.start_new_game()

    assert "Lantern City ready:" in output
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
    monkeypatch.setattr(LanternCityApp, "_generate_world_content", lambda self, on_progress=None: None)
    monkeypatch.setattr(LanternCityApp, "_generate_latent_cases", lambda self, count=2: None)

    app = LanternCityApp(
        tmp_path / "lantern-city.sqlite3",
        llm_config=OpenAICompatibleConfig(base_url="http://localhost:1234/v1", model="test-model"),
    )

    output = app.start_new_game()

    assert "Lantern City ready:" in output
    assert "Model check: warning" in output


def test_case_board_includes_actionable_recovery_section(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")
    app.talk_to_npc("npc_shrine_keeper", "Ask who last saw the missing clerk.")

    output = app.case_board()

    assert "=== Case Board: Missing Clerk ===" in output
    assert "What this suggests:" in output
    assert "Do next:" in output
    assert "Use 'leads' to rank the strongest unresolved thread." in output


def test_journal_includes_stuck_recovery_actions(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")

    output = app.journal()

    assert "=== Journal ===" in output
    assert "Do next:" in output
    assert "  - board case_missing_clerk" in output
    assert "  - leads" in output
    assert "  - compare <clue_a> <clue_b>" not in output


def test_strongest_leads_includes_recovery_footer(tmp_path) -> None:
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._introduce_case("case_missing_clerk")

    output = app.strongest_leads()

    assert "=== Strongest Leads ===" in output
    assert "What this suggests:" in output
    assert "Do next:" in output
    assert "  - board case_missing_clerk" in output
    assert "  - leads" in output


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
