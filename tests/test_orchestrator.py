from __future__ import annotations

import pytest

from lantern_city.models import CaseState, CityState, ClueState, DistrictState, LocationState, NPCState, PlayerRequest
from lantern_city.orchestrator import RequestIntent, classify_request_intent, orchestrate_request
from lantern_city.store import SQLiteStore

TURN_ZERO = "turn_0"
CITY_ID = "city_001"
DISTRICT_ID = "district_old_quarter"
LOCATION_ID = "location_shrine_lane"
NPC_ID = "npc_shrine_keeper"
CASE_ID = "case_missing_clerk"
CLUE_ID = "clue_bracket_marks"


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


@pytest.fixture
def populated_store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    store.save_objects_atomically(
        [
            CityState(
                id=CITY_ID,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                city_seed_id="cityseed_001",
                active_case_ids=[CASE_ID],
                district_ids=[DISTRICT_ID],
                faction_ids=[],
            ),
            DistrictState(
                id=DISTRICT_ID,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                name="Old Quarter",
                tone="wet and watchful",
                relevant_npc_ids=[NPC_ID],
                visible_locations=[LOCATION_ID],
            ),
            LocationState(
                id=LOCATION_ID,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                district_id=DISTRICT_ID,
                name="Shrine Lane",
                location_type="shrine",
                known_npc_ids=[NPC_ID],
                clue_ids=[CLUE_ID],
            ),
            NPCState(
                id=NPC_ID,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                name="Ila Venn",
                role_category="informant",
                district_id=DISTRICT_ID,
                location_id=LOCATION_ID,
                known_clue_ids=[CLUE_ID],
            ),
            CaseState(
                id=CASE_ID,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                title="The Missing Clerk",
                case_type="missing person",
                status="active",
                involved_district_ids=[DISTRICT_ID],
                involved_npc_ids=[NPC_ID],
                known_clue_ids=[CLUE_ID],
            ),
            ClueState(
                id=CLUE_ID,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                source_type="location",
                source_id=LOCATION_ID,
                clue_text="Fresh scoring marks on the bracket.",
                related_npc_ids=[NPC_ID],
                related_case_ids=[CASE_ID],
                related_district_ids=[DISTRICT_ID],
            ),
        ]
    )
    return store


def test_orchestrate_request_builds_active_slice_for_npc_conversation(populated_store: SQLiteStore) -> None:
    request = PlayerRequest(
        id="request_003",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        player_id="player_001",
        intent="conversation",
        target_id=NPC_ID,
    )

    orchestrated = orchestrate_request(populated_store, city_id=CITY_ID, request=request)

    assert orchestrated.request == request
    assert orchestrated.intent == "talk_to_npc"
    assert orchestrated.active_slice.working_set.city_id == CITY_ID
    assert orchestrated.active_slice.district is not None
    assert orchestrated.active_slice.district.id == DISTRICT_ID
    assert orchestrated.active_slice.location is not None
    assert orchestrated.active_slice.location.id == LOCATION_ID
    assert orchestrated.active_slice.case is not None
    assert orchestrated.active_slice.case.id == CASE_ID
    assert [npc.id for npc in orchestrated.active_slice.npcs] == [NPC_ID]
    assert [clue.id for clue in orchestrated.active_slice.clues] == [CLUE_ID]


def test_orchestrate_request_returns_controlled_empty_slice_for_generic_action_without_context(
    populated_store: SQLiteStore,
) -> None:
    request = PlayerRequest(
        id="request_004",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        player_id="player_001",
        intent="wait",
    )

    orchestrated = orchestrate_request(populated_store, city_id=CITY_ID, request=request)

    assert orchestrated.intent == "generic_action"
    assert orchestrated.active_slice.district is None
    assert orchestrated.active_slice.location is None
    assert orchestrated.active_slice.scene is None
    assert orchestrated.active_slice.case is None
    assert orchestrated.active_slice.npcs == []
    assert orchestrated.active_slice.clues == []


def test_orchestrate_request_builds_case_progression_slice_from_target_id(populated_store: SQLiteStore) -> None:
    request = PlayerRequest(
        id="request_005",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        player_id="player_001",
        intent="review case",
        target_id=CASE_ID,
    )

    orchestrated = orchestrate_request(populated_store, city_id=CITY_ID, request=request)

    assert orchestrated.intent == "case_progression"
    assert orchestrated.active_slice.case is not None
    assert orchestrated.active_slice.case.id == CASE_ID
    assert orchestrated.active_slice.working_set.case_id == CASE_ID
    assert [clue.id for clue in orchestrated.active_slice.clues] == [CLUE_ID]
