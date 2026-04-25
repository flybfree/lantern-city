from __future__ import annotations

from types import SimpleNamespace

from lantern_city.models import ClueState
from lantern_city.tui import (
    _command_reference_lines,
    _clue_reading_lines,
    _faction_pressure_lines,
    _format_command_result_markup,
    _format_start_result_markup,
    _is_new_profile_definition,
    _recovery_panel_lines,
    _should_block_generation_on_prompt_check,
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


def test_format_command_result_markup_highlights_conversation_and_scene_reads() -> None:
    rendered = _format_command_result_markup(
        "Sered Marr answers without looking up.\n"
        "How the exchange shifted:\n"
        "  - Conversation read: guarded answer with limited detail.\n"
        "What came out of it:\n"
        "  - The copied numbers were corrected after closing.\n"
        "[New lead]\n"
        "[Clue found: Ledger Trace: credible]"
    )

    assert "[bold]How the exchange shifted:[/bold]" in rendered
    assert "[bold cyan]  - Conversation read: guarded answer with limited detail.[/bold cyan]" in rendered
    assert "[bold]What came out of it:[/bold]" in rendered
    assert "[bold yellow][New lead][/bold yellow]" in rendered
    assert "[bold yellow][Clue found: Ledger Trace: credible][/bold yellow]" in rendered


def test_format_command_result_markup_highlights_inspection_read() -> None:
    rendered = _format_command_result_markup(
        "The marks line up too neatly to be wear.\n"
        "How the scene reads:\n"
        "  - Inspection read: a concrete physical sign worth following.\n"
        "What to check next:\n"
        "  - Review known clues"
    )

    assert "[bold]How the scene reads:[/bold]" in rendered
    assert "[bold cyan]  - Inspection read: a concrete physical sign worth following.[/bold cyan]" in rendered
    assert "[bold]What to check next:[/bold]" in rendered


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


def test_recovery_panel_lines_surface_social_route_summary() -> None:
    lines = _recovery_panel_lines(
        [SimpleNamespace(title="Missing Clerk", pressure_level="low")],
        clue_count=2,
        credible_count=1,
        current_case_id="case_missing_clerk",
        social_route="Ila Venn: opened a testimony route around Witness Instability",
    )

    assert any("social route: Ila Venn: opened a testimony route around Witness Instability" in line for line in lines)


def test_should_block_generation_on_prompt_check_only_blocks_failures() -> None:
    assert _should_block_generation_on_prompt_check("fail") is True
    assert _should_block_generation_on_prompt_check("warning") is False
    assert _should_block_generation_on_prompt_check("pass") is False


def test_command_reference_lines_include_core_direct_commands() -> None:
    lines = _command_reference_lines()

    assert lines[0] == "[bold]CMD Reference:[/bold]"
    assert "  start" in lines
    assert "  enter <district_id>" in lines
    assert '  inspect <location_id> "<object>"' in lines
    assert "  board [case_id]" in lines
    assert "  compare <clue_a> <clue_b>" in lines


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


def test_clue_reading_lines_surface_revealed_and_primed_states() -> None:
    lines = _clue_reading_lines(
        [
            ClueState(
                id="clue_hidden_copy_sheet",
                created_at="turn_0",
                updated_at="turn_0",
                source_type="document",
                source_id="location_archive_steps",
                clue_text="revealed document clue",
                reliability="credible",
                related_case_ids=["case_missing_clerk"],
                status="revealed",
            ),
            ClueState(
                id="clue_archive_story_conflict",
                created_at="turn_0",
                updated_at="turn_0",
                source_type="testimony",
                source_id="npc_archive_clerk",
                clue_text="primed testimony clue",
                reliability="contradicted",
                related_case_ids=["case_missing_clerk"],
                status="primed",
            ),
        ]
    )

    assert any("revealed" in line for line in lines)
    assert any("primed" in line for line in lines)
    assert any("revealed route" in line for line in lines)
    assert any("primed clue" in line for line in lines)


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


def test_is_new_profile_definition_returns_false_for_existing_named_profile() -> None:
    assert not _is_new_profile_definition(
        [
            {
                "name": "office-gemma",
                "llm_url": "http://localhost:1234/v1",
                "llm_model": "gemma",
                "prompt_profile": "default",
            }
        ],
        profile_name="office-gemma",
        url="http://localhost:1234/v1",
        model="gemma",
        prompt_profile="default",
    )


def test_is_new_profile_definition_returns_false_for_existing_endpoint_model_prompt_combo() -> None:
    assert not _is_new_profile_definition(
        [
            {
                "name": "office-gemma",
                "llm_url": "http://localhost:1234/v1",
                "llm_model": "gemma",
                "prompt_profile": "city_v2",
            }
        ],
        profile_name="new-name",
        url="http://localhost:1234/v1",
        model="gemma",
        prompt_profile="city_v2",
    )


def test_is_new_profile_definition_returns_true_for_new_profile() -> None:
    assert _is_new_profile_definition(
        [
            {
                "name": "office-gemma",
                "llm_url": "http://localhost:1234/v1",
                "llm_model": "gemma",
                "prompt_profile": "default",
            }
        ],
        profile_name="office-nemotron",
        url="http://localhost:2234/v1",
        model="nemotron",
        prompt_profile="city_v3",
    )
