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
    assert "Districts: district_lantern_ward, district_old_quarter" in output
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
    case_output = run_cli("--db", str(database_path), "case", "case_missing_clerk")

    assert "Old Quarter" in enter_output
    assert "Lanterns: dim" in enter_output
    assert "Ila Venn" in enter_output

    assert "You ask Ila Venn" in talk_output
    assert "Clue:" in talk_output
    assert "Reliability: solid" in talk_output

    assert "Lantern check" in inspect_output
    assert "location_shrine_lane" in inspect_output

    assert "Case status: solved" in case_output
    assert "Lantern understanding" in case_output
