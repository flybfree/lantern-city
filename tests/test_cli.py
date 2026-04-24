from __future__ import annotations

from io import StringIO
from pathlib import Path

from lantern_city.cli import main


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
