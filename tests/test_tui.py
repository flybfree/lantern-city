from __future__ import annotations

from types import SimpleNamespace

from lantern_city.models import ClueState
from lantern_city.tui import (
    _clue_reading_lines,
    _faction_pressure_lines,
    _format_start_result_markup,
    _recovery_panel_lines,
)


def test_format_start_result_markup_highlights_model_check_pass() -> None:
    rendered = _format_start_result_markup(
        "Lantern City ready: seeded city_lantern_city\n"
        "Startup mode: generated_runtime\n"
        "Model check: pass — startup probe validated NPC response quality in 0.8s.\n"
        "Next: enter district_old_quarter"
    )

    assert "[bold green]Lantern City ready: seeded city_lantern_city[/bold green]" in rendered
    assert "[cyan]Startup mode: generated_runtime[/cyan]" in rendered
    assert (
        "[green]Model check: pass — startup probe validated NPC response quality in 0.8s.[/green]"
        in rendered
    )


def test_format_start_result_markup_highlights_model_check_warning() -> None:
    rendered = _format_start_result_markup(
        "Lantern City ready: seeded city_lantern_city\n"
        "Startup mode: generated_runtime\n"
        "Model check: warning — startup probe failed, so NPC generation quality is uncertain.\n"
        "Next: enter district_old_quarter"
    )

    assert "[cyan]Startup mode: generated_runtime[/cyan]" in rendered
    assert (
        "[yellow]Model check: warning — startup probe failed, so NPC generation quality is uncertain.[/yellow]"
        in rendered
    )


def test_recovery_panel_lines_show_scene_recovery_when_no_clues_are_found() -> None:
    lines = _recovery_panel_lines(
        [SimpleNamespace(title="Missing Clerk", pressure_level="low")],
        clue_count=0,
        credible_count=0,
        current_location_id="location_ledger_room",
        current_case_id="case_missing_clerk",
    )

    assert any("Missing Clerk" in line for line in lines)
    assert any("inspect location_ledger_room" in line for line in lines)
    assert any("board case_missing_clerk" in line for line in lines)
    assert any("- leads" in line for line in lines)


def test_recovery_panel_lines_show_clue_interpretation_help_when_only_uncertain_clues_exist() -> None:
    lines = _recovery_panel_lines(
        [SimpleNamespace(title="Missing Clerk", pressure_level="rising")],
        clue_count=2,
        credible_count=0,
        current_npc_id="npc_shrine_keeper",
        current_case_id="case_missing_clerk",
    )

    assert any("rising pressure" in line for line in lines)
    assert any("talk npc_shrine_keeper <question>" in line for line in lines)
    assert any("board case_missing_clerk" in line for line in lines)
    assert any("- compare" in line for line in lines)


def test_recovery_panel_lines_show_resolution_support_when_credible_clues_exist() -> None:
    lines = _recovery_panel_lines(
        [SimpleNamespace(title="Missing Clerk", pressure_level="low")],
        clue_count=3,
        credible_count=1,
        current_case_id="case_missing_clerk",
    )

    assert any("- leads" in line for line in lines)
    assert any("board case_missing_clerk" in line for line in lines)


def test_recovery_panel_lines_surface_records_pressure_guidance() -> None:
    lines = _recovery_panel_lines(
        [SimpleNamespace(title="Missing Clerk", pressure_level="rising")],
        clue_count=3,
        credible_count=1,
        current_case_id="case_missing_clerk",
        institutional_pressure="Memory Keepers is degrading paper certainty and smothering the record trail",
    )

    assert any("catch record inconsistencies before they settle into the official version" in line for line in lines)
    assert any("press on ledgers, copies, and corroborating records" in line for line in lines)


def test_recovery_panel_lines_surface_civic_pressure_guidance() -> None:
    lines = _recovery_panel_lines(
        [SimpleNamespace(title="Missing Clerk", pressure_level="rising")],
        clue_count=3,
        credible_count=1,
        current_case_id="case_missing_clerk",
        current_npc_id="npc_archive_clerk",
        institutional_pressure="Council of Lights is constricting access and hardening witnesses through procedure",
    )

    assert any("talk npc_archive_clerk <question>" in line for line in lines)
    assert any("before procedure hardens the witness picture" in line for line in lines)
    assert any("people and places are still reachable before access closes" in line for line in lines)


def test_recovery_panel_lines_fall_back_to_generic_scene_hint_without_location_or_npc() -> None:
    lines = _recovery_panel_lines(
        [SimpleNamespace(title="Missing Clerk", pressure_level="low")],
        clue_count=0,
        credible_count=0,
    )

    assert any("- matters" in line for line in lines)


def test_recovery_panel_lines_support_generated_case_ids() -> None:
    lines = _recovery_panel_lines(
        [SimpleNamespace(title="Borrowed Ledger", pressure_level="rising")],
        clue_count=2,
        credible_count=1,
        current_case_id="case_gen_002",
    )

    assert any("Borrowed Ledger" in line for line in lines)
    assert any("board case_gen_002" in line for line in lines)


def test_clue_reading_lines_surface_support_contradiction_and_follow_up() -> None:
    lines = _clue_reading_lines(
        [
            ClueState(
                id="clue_missing_clerk_ledgers",
                created_at="turn_0",
                updated_at="turn_0",
                source_type="document",
                source_id="location_shrine_lane",
                clue_text="ledger clue",
                reliability="credible",
                related_case_ids=["case_missing_clerk"],
            ),
            ClueState(
                id="clue_family_record_discrepancy",
                created_at="turn_0",
                updated_at="turn_0",
                source_type="document",
                source_id="location_archive_steps",
                clue_text="contradicted clue",
                reliability="contradicted",
                related_case_ids=["case_missing_clerk"],
            ),
            ClueState(
                id="clue_missing_maintenance_line",
                created_at="turn_0",
                updated_at="turn_0",
                source_type="document",
                source_id="location_ledger_room",
                clue_text="follow-up clue",
                reliability="uncertain",
                related_case_ids=["case_missing_clerk"],
            ),
        ]
    )

    assert any("support" in line for line in lines)
    assert any("contradict" in line for line in lines)
    assert any("follow-up" in line for line in lines)
    assert any("supports case" in line for line in lines)
    assert any("contradiction" in line for line in lines)
    assert any("paper trail" in line for line in lines)


def test_faction_pressure_lines_surface_attitude_and_plan() -> None:
    lines = _faction_pressure_lines(
        [
            SimpleNamespace(
                name="Memory Keepers",
                public_goal="preserve continuity",
                hidden_goal="control what the city remembers",
                known_assets=["memory stewardship", "records", "certification"],
                attitude_toward_player="guarded",
                active_plans=["contain scrutiny in district_old_quarter", "procedural delay"],
            ),
            SimpleNamespace(
                name="Council of Lights",
                public_goal="maintain public order",
                hidden_goal="monopolize lantern legitimacy",
                known_assets=["civic lantern administration", "compliance", "access permits"],
                attitude_toward_player="wary",
                active_plans=["official review", "manage missing clerk fallout"],
            ),
        ]
    )

    assert any("Memory Keepers: guarded / records control / tightening official scrutiny" in line for line in lines)
    assert any("Council of Lights: wary / civic enforcement / tightening official scrutiny" in line for line in lines)
