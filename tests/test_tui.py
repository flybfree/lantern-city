from __future__ import annotations

from types import SimpleNamespace

from lantern_city.tui import _format_start_result_markup, _recovery_panel_lines


def test_format_start_result_markup_highlights_model_check_pass() -> None:
    rendered = _format_start_result_markup(
        "Lantern City ready: seeded city_lantern_city\n"
        "Model check: pass — startup probe validated NPC response quality in 0.8s.\n"
        "Next: enter district_old_quarter"
    )

    assert "[bold green]Lantern City ready: seeded city_lantern_city[/bold green]" in rendered
    assert (
        "[green]Model check: pass — startup probe validated NPC response quality in 0.8s.[/green]"
        in rendered
    )


def test_format_start_result_markup_highlights_model_check_warning() -> None:
    rendered = _format_start_result_markup(
        "Lantern City ready: seeded city_lantern_city\n"
        "Model check: warning — startup probe failed, so NPC generation quality is uncertain.\n"
        "Next: enter district_old_quarter"
    )

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


def test_recovery_panel_lines_fall_back_to_generic_scene_hint_without_location_or_npc() -> None:
    lines = _recovery_panel_lines(
        [SimpleNamespace(title="Missing Clerk", pressure_level="low")],
        clue_count=0,
        credible_count=0,
    )

    assert any("- matters" in line for line in lines)
