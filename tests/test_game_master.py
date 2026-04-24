from __future__ import annotations

from lantern_city.case_bootstrap import bootstrap_generated_case
from lantern_city.app import LanternCityApp
from lantern_city.cases import transition_case
from lantern_city.generation.case_generation import (
    CaseGenerationResult,
    GeneratedClueSpec,
    GeneratedNPCSpec,
    GeneratedResolutionPath,
)
from lantern_city.game_master import GameMaster


class _RecordingLLM:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_json(self, *, messages, temperature, max_tokens, schema):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "schema": schema,
            }
        )
        return {"narrative": "You pause over the lead and feel the city tighten around it."}


def test_narrate_includes_explicit_new_lead_guidance_in_system_prompt() -> None:
    llm = _RecordingLLM()
    gm = GameMaster(app=None, llm=llm)  # type: ignore[arg-type]

    narrative = gm._narrate(
        "look closer",
        ["inspect location_archive_steps"],
        [
            "[command ok: inspect location_archive_steps]\n"
            "The marks line up too neatly to be wear.\n"
            "[New lead]\n"
            "What you learned:\n"
            "  - Notable clue: Someone maintained this route after it should have gone dark."
        ],
        "Current district: Old Quarter",
    )

    assert narrative == "You pause over the lead and feel the city tighten around it."
    system_prompt = llm.calls[0]["messages"][0]["content"]
    user_prompt = llm.calls[0]["messages"][1]["content"]

    assert 'If the game events include a "[New lead]" tag' in system_prompt
    assert "The player uncovered a significant lead whose full meaning is not yet established." in user_prompt


def test_narrate_only_marks_direct_dialogue_for_successful_talk_results() -> None:
    llm = _RecordingLLM()
    gm = GameMaster(app=None, llm=llm)  # type: ignore[arg-type]

    gm._narrate(
        "what changed",
        ["inspect location_archive_steps"],
        [
            "[command ok: inspect location_archive_steps]\n"
            "What you learned:\n"
            "  - A careful player-facing summary."
        ],
        "Current district: Old Quarter",
    )

    user_prompt = llm.calls[0]["messages"][1]["content"]
    assert "A successful conversation happened and produced concrete information." not in user_prompt


def test_narrate_adds_recovery_guidance_for_orientation_requests(tmp_path) -> None:
    llm = _RecordingLLM()
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app.go("location_ledger_room")
    app._introduce_case("case_missing_clerk")
    gm = GameMaster(app=app, llm=llm)

    gm._narrate(
        "what should I do next?",
        [],
        [],
        gm._build_context(),
    )

    system_prompt = llm.calls[0]["messages"][0]["content"]
    user_prompt = llm.calls[0]["messages"][1]["content"]

    assert "treat the turn as a recovery or orientation request" in system_prompt
    assert "Recovery guidance:" in user_prompt
    assert "The player is asking for orientation about what matters or what to do next." in user_prompt
    assert "location_ledger_room" in user_prompt
    assert "npc_archive_clerk" in user_prompt
    assert "board case_missing_clerk" in user_prompt


def test_narrate_recovery_guidance_shifts_to_compare_when_only_uncertain_clues_exist(tmp_path) -> None:
    llm = _RecordingLLM()
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    app._acquire_clues(["clue_missing_maintenance_line"])
    gm = GameMaster(app=app, llm=llm)

    gm._narrate(
        "I'm stuck",
        [],
        [],
        gm._build_context(),
    )

    user_prompt = llm.calls[0]["messages"][1]["content"]

    assert "none are yet credible" in user_prompt
    assert "Compare is appropriate if two clues seem related or inconsistent." in user_prompt


def test_narrate_recovery_guidance_supports_generated_case_ids(tmp_path) -> None:
    llm = _RecordingLLM()
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")

    city = app._require_city()
    generated = CaseGenerationResult(
        request_id="req_case_002",
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
                starting_reliability="uncertain",
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
        store=app.store,
        city=city,
        case_index=2,
        updated_at="turn_test",
    )
    active_case = transition_case(bootstrap.case, "active", updated_at="turn_test_active")
    app.store.save_objects_atomically(
        [
            active_case,
            *bootstrap.npcs,
            *bootstrap.clues,
            *bootstrap.updated_locations,
            *bootstrap.updated_districts,
            bootstrap.updated_city,
        ]
    )
    app._introduce_case(active_case.id)
    app._acquire_clues([bootstrap.clues[0].id])

    gm = GameMaster(app=app, llm=llm)
    gm._narrate("what should I do next?", [], [], gm._build_context())

    user_prompt = llm.calls[0]["messages"][1]["content"]

    assert "Borrowed Ledger" in user_prompt
    assert "case_gen_002" in user_prompt
    assert "board case_gen_002" in user_prompt


def test_build_context_includes_clue_readability_distinctions(tmp_path) -> None:
    llm = _RecordingLLM()
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
    gm = GameMaster(app=app, llm=llm)

    context = gm._build_context()

    assert "Clue reading:" in context
    assert "role=supports current case" in context
    assert "role=contradiction to explain" in context
    assert "role=paper trail to test" in context
    assert "Why it matters:" in context


def test_build_context_includes_social_pressure_for_current_npc(tmp_path) -> None:
    llm = _RecordingLLM()
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
                "relationships": {
                    **npc.relationships,
                    "player": npc.relationships["player"].model_copy(update={"status": "guarded"}),
                    npc.loyalty: npc.relationships[npc.loyalty].model_copy(update={"status": "aligned"}),
                },
            }
        )
    )
    gm = GameMaster(app=app, llm=llm)

    context = gm._build_context()

    assert "Social pressure:" in context
    assert "Ila Venn (npc_shrine_keeper) state=obstructing" in context
    assert "player=guarded" in context
    assert "loyalty=faction_memory_keepers:aligned" in context


def test_build_context_includes_faction_posture_summary(tmp_path) -> None:
    llm = _RecordingLLM()
    app = LanternCityApp(tmp_path / "lantern-city.sqlite3")
    app.start_new_game()
    app.enter_district("district_old_quarter")
    faction = app.store.load_object("FactionState", "faction_memory_keepers")
    assert faction is not None
    app.store.save_object(
        faction.model_copy(
            update={
                "attitude_toward_player": "guarded",
                "active_plans": ["contain scrutiny in district_old_quarter"],
            }
        )
    )
    gm = GameMaster(app=app, llm=llm)

    context = gm._build_context()

    assert "Faction posture:" in context
    assert (
        "Memory Keepers: guarded toward you, focused on district_old_quarter, plan 'contain scrutiny in district_old_quarter'"
        in context
    )


def test_narrate_system_prompt_mentions_clue_role_distinctions() -> None:
    llm = _RecordingLLM()
    gm = GameMaster(app=None, llm=llm)  # type: ignore[arg-type]

    gm._narrate(
        "what matters here?",
        [],
        [],
        "Current district: Old Quarter\nClue reading:\n  Ledger Trail [credible] role=supports current case",
    )

    system_prompt = llm.calls[0]["messages"][0]["content"]

    assert "preserve those distinctions in the narration" in system_prompt
    assert "When a clue is marked as a contradiction" in system_prompt
