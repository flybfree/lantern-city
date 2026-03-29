from __future__ import annotations

from pathlib import Path

from lantern_city.app import LanternCityApp


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
    assert "Clue: clue_missing_clerk_ledgers" in talk_output
    assert "[Lantern: dim" in inspect_output
    assert "Case status: solved" in case_output

    reloaded = LanternCityApp(database_path)
    snapshot = reloaded.get_state_snapshot()

    assert snapshot["city_id"] == "city_lantern_city"
    assert snapshot["case_status"] == "solved"
    assert snapshot["clue_reliability"] == "solid"
    assert snapshot["lantern_condition"] == "dim"
    assert snapshot["npc_memory_count"] == 1
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
