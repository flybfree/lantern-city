from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from lantern_city.app import LanternCityApp, _load_default_seed
from lantern_city.cli import _default_player_startup_mode, _load_startup_mode, main
from lantern_city.prompt_diagnostics import PromptCheckStageResult, PromptDiagnosticsReport
from lantern_city.seed_schema import validate_city_seed


def run_cli(*args: str) -> str:
    buffer = StringIO()
    exit_code = main(list(args), stdout=buffer)
    assert exit_code == 0
    return buffer.getvalue()


def test_cli_start_initializes_a_game_and_renders_compact_status(tmp_path: Path) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"

    output = run_cli("--db", str(database_path), "start")

    assert "Lantern City ready" in output
    assert "district_old_quarter" in output
    assert "district_lantern_ward" in output
    assert "Startup mode: mvp_baseline" in output
    assert "Active case: The Missing Clerk" in output
    assert "Next: enter district_old_quarter" in output


def test_cli_supports_a_minimal_playable_command_loop(tmp_path: Path) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"

    run_cli("--db", str(database_path), "start")
    enter_output = run_cli("--db", str(database_path), "enter", "district_old_quarter")
    talk_output = run_cli(
        "--db",
        str(database_path),
        "talk",
        "npc_shrine_keeper",
        "Ask who last saw the missing clerk.",
    )
    inspect_output = run_cli("--db", str(database_path), "inspect", "location_shrine_lane")
    run_cli("--db", str(database_path), "inspect", "location_service_passage")
    case_output = run_cli("--db", str(database_path), "case", "case_missing_clerk")

    assert "Old Quarter" in enter_output
    assert "Lanterns: dim" in enter_output
    assert "Ila Venn" in enter_output
    assert "Available NPC IDs:" in enter_output
    assert "npc_shrine_keeper (Ila Venn)" in enter_output
    assert "npc_archive_clerk (Sered Marr)" in enter_output
    assert "location_shrine_lane" in enter_output
    assert "location_archive_steps" in enter_output

    assert "You ask Ila Venn" in talk_output
    assert "[Clue" in talk_output
    assert "solid" in talk_output

    assert "[Lantern:" in inspect_output
    assert "Shrine Lane" in inspect_output

    assert "Case status: solved" in case_output
    assert "Lantern understanding" in case_output


def test_cli_returns_helpful_error_for_unknown_npc_in_current_slice(tmp_path: Path) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"

    run_cli("--db", str(database_path), "start")
    run_cli("--db", str(database_path), "enter", "district_old_quarter")
    output = run_cli(
        "--db",
        str(database_path),
        "talk",
        "npc_sered_marr",
        "Ask about the missing clerk.",
    )

    assert "Missing required world object NPCState:npc_sered_marr" in output
    assert "Hint: run `enter <district_id>` first and use one of the IDs shown in the district output." in output


def test_cli_startup_mode_can_force_mvp_baseline_even_with_llm_config(tmp_path: Path) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"

    output = run_cli(
        "--db",
        str(database_path),
        "--llm-url",
        "http://localhost:1234/v1",
        "--llm-model",
        "test-model",
        "--startup-mode",
        "mvp_baseline",
        "start",
    )

    assert "Active case: The Missing Clerk" in output
    assert "Startup mode: mvp_baseline" in output
    assert "Model check:" not in output


def test_cli_reports_invalid_generated_runtime_without_llm(tmp_path: Path) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"

    output = run_cli(
        "--db",
        str(database_path),
        "--startup-mode",
        "generated_runtime",
        "start",
    )

    assert "Error: startup_mode='generated_runtime' requires llm_config" in output


def test_cli_persists_startup_mode_with_llm_config(tmp_path: Path) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"

    run_cli(
        "--db",
        str(database_path),
        "--llm-url",
        "http://localhost:1234/v1",
        "--llm-model",
        "test-model",
        "--startup-mode",
        "mvp_baseline",
        "start",
    )

    config = json.loads(database_path.with_suffix(".json").read_text(encoding="utf-8"))

    assert config["startup_mode"] == "mvp_baseline"
    assert _load_startup_mode(str(database_path)) == "mvp_baseline"


def test_cli_defaults_to_generated_runtime_when_llm_is_present_and_no_mode_is_specified(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"

    monkeypatch.setattr(
        LanternCityApp,
        "_generate_city_seed",
        lambda self, concept=None, on_progress=None: validate_city_seed(_load_default_seed()),
    )
    monkeypatch.setattr(LanternCityApp, "_generate_world_content", lambda self, on_progress=None: None)
    monkeypatch.setattr(LanternCityApp, "_generate_latent_cases", lambda self, count=2: None)

    run_cli(
        "--db",
        str(database_path),
        "--llm-url",
        "http://localhost:1234/v1",
        "--llm-model",
        "test-model",
        "start",
    )

    config = json.loads(database_path.with_suffix(".json").read_text(encoding="utf-8"))

    assert config["startup_mode"] == "generated_runtime"


def test_default_player_startup_mode_prefers_generated_runtime_when_llm_exists() -> None:
    assert _default_player_startup_mode(has_llm_config=True) == "generated_runtime"
    assert _default_player_startup_mode(has_llm_config=False) == "mvp_baseline"


def test_cli_prompt_check_requires_llm_config(tmp_path: Path) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"

    output = run_cli("--db", str(database_path), "prompt-check")

    assert "Error: prompt-check requires llm_config" in output


def test_cli_prompt_check_renders_report_and_can_save_json(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "lantern-city.sqlite3"
    report_path = tmp_path / "prompt-check.json"

    def _fake_prompt_check(*, llm_config, concept=""):
        assert llm_config.model == "test-model"
        assert concept == "fog-bound records city"
        return PromptDiagnosticsReport(
            base_url=llm_config.base_url,
            model=llm_config.model,
            concept=concept,
            stages=[
                PromptCheckStageResult(
                    name="startup_probe",
                    status="pass",
                    elapsed_seconds=0.4,
                    summary="NPC probe validated with confidence 0.92",
                    sample="A careful witness points you toward the archive cart.",
                )
            ],
        )

    monkeypatch.setattr("lantern_city.cli.run_prompt_diagnostics", _fake_prompt_check)

    output = run_cli(
        "--db",
        str(database_path),
        "--llm-url",
        "http://localhost:1234/v1",
        "--llm-model",
        "test-model",
        "prompt-check",
        "--concept",
        "fog-bound records city",
        "--report",
        str(report_path),
    )

    assert "=== Prompt Check ===" in output
    assert "Overall: pass" in output
    assert "startup_probe" in output
    assert "Report saved:" in output

    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["model"] == "test-model"
    assert report_payload["overall_status"] == "pass"
