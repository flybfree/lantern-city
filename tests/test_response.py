from __future__ import annotations

from lantern_city.response import ResponsePayload, compose_response


def test_compose_response_includes_required_fields_and_compact_text() -> None:
    response = compose_response(
        narrative_text="You step into the Old Quarter beneath a dim lantern line.",
        state_changes=["Presence increased in Old Quarter."],
        learned=["The district lanterns are running dim."],
        now_available=["Travel to Shrine Lane", "Speak to Ila Venn"],
        next_actions=["Inspect the shrine bracket", "Review the missing clerk case"],
    )

    assert isinstance(response, ResponsePayload)
    assert response.narrative_text == "You step into the Old Quarter beneath a dim lantern line."
    assert response.state_changes == ["Presence increased in Old Quarter."]
    assert response.learned == ["The district lanterns are running dim."]
    assert response.now_available == ["Travel to Shrine Lane", "Speak to Ila Venn"]
    assert response.next_actions == ["Inspect the shrine bracket", "Review the missing clerk case"]
    assert response.text == (
        "What happened: You step into the Old Quarter beneath a dim lantern line.\n"
        "What changed: Presence increased in Old Quarter.\n"
        "What you learned: The district lanterns are running dim.\n"
        "Now available: Travel to Shrine Lane; Speak to Ila Venn\n"
        "Next actions: Inspect the shrine bracket; Review the missing clerk case"
    )
