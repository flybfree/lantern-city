from __future__ import annotations

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
