from __future__ import annotations

import pytest

from lantern_city.models import PlayerRequest
from lantern_city.orchestrator import RequestIntent, classify_request_intent


@pytest.mark.parametrize(
    ("raw_intent", "expected"),
    [
        ("district entry", "district_entry"),
        ("enter_district", "district_entry"),
        ("talk to NPC", "talk_to_npc"),
        ("conversation", "talk_to_npc"),
        ("inspect location", "inspect_location"),
        ("investigate", "inspect_location"),
        ("case progression", "case_progression"),
        ("review case", "case_progression"),
        ("wait", "generic_action"),
    ],
)
def test_classify_request_intent_maps_supported_intents(
    raw_intent: str, expected: RequestIntent
) -> None:
    request = PlayerRequest(
        id="request_001",
        created_at="turn_0",
        updated_at="turn_0",
        player_id="player_001",
        intent=raw_intent,
    )

    assert classify_request_intent(request) == expected


def test_classify_request_intent_normalizes_case_and_whitespace() -> None:
    request = PlayerRequest(
        id="request_002",
        created_at="turn_0",
        updated_at="turn_0",
        player_id="player_001",
        intent="  Talk To Npc  ",
    )

    assert classify_request_intent(request) == "talk_to_npc"
