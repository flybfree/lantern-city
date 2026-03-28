from __future__ import annotations

import pytest

from lantern_city.active_slice import ActiveSlice
from lantern_city.models import (
    ActiveWorkingSet,
    CaseState,
    CityState,
    ClueState,
    DistrictState,
    LocationState,
    NPCState,
    PlayerRequest,
)
from lantern_city.orchestrator import OrchestratedRequest
from lantern_city.store import SQLiteStore

TURN_ZERO = "turn_0"
TURN_ONE = "turn_1"
CITY_ID = "city_001"
DISTRICT_ID = "district_old_quarter"
LOCATION_ID = "location_shrine_lane"
NPC_ID = "npc_shrine_keeper"
CASE_ID = "case_missing_clerk"
CLUE_ID = "clue_bracket_marks"


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
                lantern_condition="dim",
                visible_locations=[LOCATION_ID],
                relevant_npc_ids=[NPC_ID],
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
                public_identity="shrine keeper",
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
                clue_text="Fresh scoring marks suggest recent tampering.",
                related_npc_ids=[NPC_ID],
                related_case_ids=[CASE_ID],
                related_district_ids=[DISTRICT_ID],
            ),
        ]
    )
    return store


def make_request(
    *,
    intent: str,
    target_id: str | None = None,
    input_text: str = "",
) -> PlayerRequest:
    return PlayerRequest(
        id=f"request_{intent.replace(' ', '_')}",
        created_at=TURN_ONE,
        updated_at=TURN_ONE,
        player_id="player_001",
        intent=intent,
        target_id=target_id,
        input_text=input_text,
    )


def _district_entry_slice(request: PlayerRequest) -> ActiveSlice:
    district = DistrictState(
        id=DISTRICT_ID,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        name="Old Quarter",
        tone="wet and watchful",
        lantern_condition="dim",
        visible_locations=[LOCATION_ID],
        relevant_npc_ids=[NPC_ID],
    )
    npc = NPCState(
        id=NPC_ID,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        name="Ila Venn",
        role_category="informant",
        district_id=DISTRICT_ID,
        location_id=LOCATION_ID,
        public_identity="shrine keeper",
        known_clue_ids=[CLUE_ID],
    )
    clue = ClueState(
        id=CLUE_ID,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        source_type="location",
        source_id=LOCATION_ID,
        clue_text="Fresh scoring marks suggest recent tampering.",
        related_npc_ids=[NPC_ID],
        related_case_ids=[CASE_ID],
        related_district_ids=[DISTRICT_ID],
    )
    case = CaseState(
        id=CASE_ID,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        title="The Missing Clerk",
        case_type="missing person",
        status="active",
        involved_district_ids=[DISTRICT_ID],
        involved_npc_ids=[NPC_ID],
        known_clue_ids=[CLUE_ID],
    )
    return ActiveSlice(
        working_set=ActiveWorkingSet(
            id=f"synthetic_active_working_set_{CITY_ID}_{request.id}",
            created_at=f"synthetic_active_slice_request_{request.id}",
            updated_at=f"synthetic_active_slice_request_{request.id}",
            city_id=CITY_ID,
            district_id=DISTRICT_ID,
            npc_ids=[NPC_ID],
            clue_ids=[CLUE_ID],
            case_id=CASE_ID,
        ),
        district=district,
        location=None,
        scene=None,
        npcs=[npc],
        clues=[clue],
        case=case,
    )


def test_handle_player_request_uses_orchestrator_to_build_the_active_slice(
    populated_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lantern_city import engine

    request = make_request(intent="district entry", target_id=DISTRICT_ID)
    expected_slice = _district_entry_slice(request)
    calls: list[tuple[SQLiteStore, str, PlayerRequest]] = []

    def fake_orchestrate_request(
        store: SQLiteStore,
        *,
        city_id: str,
        request: PlayerRequest,
    ) -> OrchestratedRequest:
        calls.append((store, city_id, request))
        return OrchestratedRequest(
            request=request,
            intent="district_entry",
            active_slice=expected_slice,
        )

    monkeypatch.setattr(engine, "orchestrate_request", fake_orchestrate_request)

    outcome = engine.handle_player_request(populated_store, city_id=CITY_ID, request=request)

    assert calls == [(populated_store, CITY_ID, request)]
    assert outcome.intent == "district_entry"
    assert outcome.active_slice == expected_slice


def test_handle_player_request_routes_district_entry_updates_through_state_update_engine(
    populated_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lantern_city import engine

    request = make_request(intent="district entry", target_id=DISTRICT_ID)
    applied_objects: list[object] = []

    def fake_apply_updates(self, *objects):
        applied_objects.extend(objects)
        return [f"{obj.type}:{obj.id}" for obj in objects]

    monkeypatch.setattr(engine.StateUpdateEngine, "apply_updates", fake_apply_updates)

    outcome = engine.handle_player_request(populated_store, city_id=CITY_ID, request=request)

    assert outcome.changed_objects == [f"CityState:{CITY_ID}"]
    assert len(applied_objects) == 1
    updated_city = applied_objects[0]
    assert isinstance(updated_city, CityState)
    assert updated_city.id == CITY_ID
    assert updated_city.player_presence_level == pytest.approx(0.1)
    assert updated_city.version == 2
    assert updated_city.updated_at == TURN_ONE



def test_handle_player_request_returns_district_entry_response_and_persists_city_update(
    populated_store: SQLiteStore,
) -> None:
    from lantern_city.engine import handle_player_request

    request = make_request(intent="district entry", target_id=DISTRICT_ID)

    outcome = handle_player_request(populated_store, city_id=CITY_ID, request=request)
    city = populated_store.load_object("CityState", CITY_ID)
    district = populated_store.load_object("DistrictState", DISTRICT_ID)
    cached = populated_store.load_cache(f"response:district_entry:{DISTRICT_ID}")

    assert outcome.response.narrative_text == (
        "You enter Old Quarter. The district feels wet and watchful, "
        "and the lanterns are dim."
    )
    assert outcome.response.state_changes == ["Presence increased in Old Quarter."]
    assert outcome.response.learned == ["The district lanterns are running dim."]
    assert outcome.response.now_available == ["Travel to Shrine Lane", "Speak to Ila Venn"]
    assert outcome.response.next_actions == ["Inspect Shrine Lane", "Review The Missing Clerk"]
    assert city is not None
    assert isinstance(city, CityState)
    assert city.player_presence_level == pytest.approx(0.1)
    assert city.version == 2
    assert city.updated_at == TURN_ONE
    assert district is not None
    assert isinstance(district, DistrictState)
    assert district.version == 1
    assert district.updated_at == TURN_ZERO
    assert cached is not None
    assert cached["payload"]["narrative_text"] == outcome.response.narrative_text


def test_handle_player_request_returns_npc_conversation_response_and_only_mutates_npc(
    populated_store: SQLiteStore,
) -> None:
    from lantern_city.engine import handle_player_request

    request = make_request(
        intent="conversation",
        target_id=NPC_ID,
        input_text="Ask about the outage.",
    )

    outcome = handle_player_request(populated_store, city_id=CITY_ID, request=request)
    city = populated_store.load_object("CityState", CITY_ID)
    district = populated_store.load_object("DistrictState", DISTRICT_ID)
    npc = populated_store.load_object("NPCState", NPC_ID)
    cached = populated_store.load_cache(f"response:talk_to_npc:{NPC_ID}:ask about the outage")

    assert outcome.intent == "talk_to_npc"
    assert outcome.response.narrative_text == (
        'You ask Ila Venn, shrine keeper, "Ask about the outage." '
        "She answers carefully and stays close to what is already known."
    )
    assert outcome.response.state_changes == ["Recorded a new conversation beat with Ila Venn."]
    assert outcome.response.learned == ["Fresh scoring marks suggest recent tampering."]
    assert outcome.response.now_available == ["Inspect Shrine Lane", "Press Ila Venn for specifics"]
    assert outcome.response.next_actions == ["Ask a narrower question", "Review The Missing Clerk"]
    assert city is not None
    assert isinstance(city, CityState)
    assert city.version == 1
    assert city.updated_at == TURN_ZERO
    assert district is not None
    assert isinstance(district, DistrictState)
    assert district.version == 1
    assert district.updated_at == TURN_ZERO
    assert npc is not None
    assert isinstance(npc, NPCState)
    assert npc.version == 2
    assert npc.updated_at == TURN_ONE
    assert npc.memory_log == [
        {
            "request_id": request.id,
            "intent": "talk_to_npc",
            "input_text": "Ask about the outage.",
        }
    ]
    assert cached is not None
    assert cached["payload"]["next_actions"] == [
        "Ask a narrower question",
        "Review The Missing Clerk",
    ]
