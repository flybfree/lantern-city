from __future__ import annotations

from pathlib import Path

from lantern_city.case_bootstrap import bootstrap_generated_case
from lantern_city.app import LanternCityApp, _load_default_seed
from lantern_city.cases import transition_case
from lantern_city.generation.case_generation import (
    CaseGenerationResult,
    GeneratedClueSpec,
    GeneratedNPCSpec,
    GeneratedResolutionPath,
)
from lantern_city.llm_client import OpenAICompatibleConfig
from lantern_city.models import CaseState
from lantern_city.seed_schema import validate_city_seed


def test_end_to_end_flow_bootstraps_seed_and_advances_case_with_persistence(tmp_path: Path) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"
    app = LanternCityApp(database_path)

    start_output = app.start_new_game()
    enter_output = app.run_command("enter district_old_quarter")
    talk_output = app.run_command("talk npc_shrine_keeper Ask who last saw the missing clerk.")
    inspect_output = app.run_command("inspect location_shrine_lane")
    app.run_command("inspect location_service_passage")
    case_output = app.run_command("case case_missing_clerk")

    assert "seeded city_lantern_city" in start_output
    assert "Old Quarter" in enter_output
    assert "Ila Venn" in talk_output
    assert "[Clue" in talk_output
    assert "[Lantern: dim" in inspect_output
    assert "Case status: solved" in case_output

    reloaded = LanternCityApp(database_path)
    snapshot = reloaded.get_state_snapshot()

    assert snapshot["city_id"] == "city_lantern_city"
    assert snapshot["case_status"] == "solved"
    assert snapshot["clue_reliability"] == "solid"
    assert snapshot["lantern_condition"] == "dim"
    assert snapshot["npc_memory_count"] >= 2
    assert snapshot["lantern_understanding_score"] > 18


def test_end_to_end_loop_is_idempotent_for_start_and_keeps_existing_state(tmp_path: Path) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"
    app = LanternCityApp(database_path)

    app.start_new_game()
    app.run_command("talk npc_shrine_keeper Press on the ledger marks.")
    first_snapshot = app.get_state_snapshot()

    restarted = LanternCityApp(database_path)
    output = restarted.start_new_game()
    second_snapshot = restarted.get_state_snapshot()

    assert "Existing game loaded" in output
    assert second_snapshot["city_id"] == first_snapshot["city_id"]
    assert second_snapshot["npc_memory_count"] == first_snapshot["npc_memory_count"]
    assert second_snapshot["clue_reliability"] == first_snapshot["clue_reliability"]


def test_end_to_end_generated_runtime_bootstraps_and_persists_generated_case(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"

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

    def fake_world_content(self, on_progress=None) -> None:
        self._seed_authored_scene_objects()

    def fake_latent_cases(self, count=2) -> None:
        city = self._require_city()
        existing_cases = [
            obj
            for obj in self.store.list_objects("CaseState")
            if isinstance(obj, CaseState)
        ]
        gen_case_count = sum(1 for obj in existing_cases if obj.id.startswith("case_gen_"))
        generated = CaseGenerationResult(
            request_id="req_case_e2e_001",
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
                    source_type="physical",
                    district_id="district_old_quarter",
                    location_type_hint="records",
                    clue_text="Ink scoring on a ledger shelf suggests a page was removed in haste.",
                    starting_reliability="credible",
                    known_by_npc_index=None,
                ),
                GeneratedClueSpec(
                    source_type="testimony",
                    district_id="district_the_docks",
                    location_type_hint="office",
                    clue_text="A dock runner swears the copied numbers changed after the lamps were dimmed.",
                    starting_reliability="uncertain",
                    known_by_npc_index=None,
                ),
            ],
            resolution_paths=[
                GeneratedResolutionPath(
                    path_id="best_path",
                    label="Trace the copied ledger",
                    outcome_status="solved",
                    required_clue_indices=[0, 1],
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
            generated,
            store=self.store,
            city=city,
            case_index=gen_case_count,
            updated_at="turn_test",
        )
        self.store.save_objects_atomically(
            [
                bootstrap.case,
                *bootstrap.npcs,
                *bootstrap.clues,
                *bootstrap.updated_locations,
                *bootstrap.updated_districts,
                bootstrap.updated_city,
            ]
        )

    monkeypatch.setattr(LanternCityApp, "_generate_world_content", fake_world_content)
    monkeypatch.setattr(LanternCityApp, "_generate_latent_cases", fake_latent_cases)

    app = LanternCityApp(
        database_path,
        llm_config=OpenAICompatibleConfig(base_url="http://localhost:1234/v1", model="test-model"),
        startup_mode="generated_runtime",
    )

    start_output = app.start_new_game()
    assert "Startup mode: generated_runtime" in start_output
    assert "Model check: pass" in start_output

    case = app.store.load_object("CaseState", "case_gen_000")
    assert isinstance(case, CaseState)
    active_case = transition_case(case, "active", updated_at="turn_test_active")
    app.store.save_object(active_case)
    app._introduce_case(active_case.id)
    app._acquire_clues(["clue_case_gen_000_00", "clue_case_gen_000_01"])

    case_output = app.run_command("case case_gen_000")

    assert "Case status: solved" in case_output
    assert "Case: Borrowed Ledger" in case_output

    reloaded = LanternCityApp(
        database_path,
        llm_config=OpenAICompatibleConfig(base_url="http://localhost:1234/v1", model="test-model"),
        startup_mode="generated_runtime",
    )
    reload_output = reloaded.start_new_game()
    reloaded_case = reloaded.store.load_object("CaseState", "case_gen_000")

    assert "Existing game loaded" in reload_output
    assert "Startup mode: generated_runtime" in reload_output
    assert isinstance(reloaded_case, CaseState)
    assert reloaded_case.status == "solved"
