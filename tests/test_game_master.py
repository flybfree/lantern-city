from __future__ import annotations

from lantern_city.app import LanternCityApp
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
