from __future__ import annotations

from dataclasses import replace

import pytest

from lantern_city.active_slice import ActiveSlice
from lantern_city.models import (
    ActiveWorkingSet,
    CaseState,
    CityState,
    ClueState,
    DistrictState,
    FactionState,
    LocationState,
    NPCState,
    PlayerRequest,
)
from lantern_city.generation.npc_response import NPCResponseGenerationResult
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
        city=CityState(
            id=CITY_ID,
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            city_seed_id="cityseed_001",
            active_case_ids=[CASE_ID],
            district_ids=[DISTRICT_ID],
            faction_ids=[],
        ),
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
    assert outcome.active_slice.city.id == CITY_ID


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

    assert outcome.response.narrative_text == (
        "You enter Old Quarter. The lanterns are dim."
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
    assert populated_store.load_cache(f"response:district_entry:{DISTRICT_ID}") is None


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

    assert outcome.intent == "talk_to_npc"
    assert outcome.response.narrative_text == (
        'You ask Ila Venn, shrine keeper, "Ask about the outage." '
        "They answer carefully and stay close to what is already known."
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
            "memory_type": "conversation",
            "turn": TURN_ONE,
            "request_id": request.id,
            "intent": "talk_to_npc",
            "input_text": "Ask about the outage.",
            "related_case_ids": [CASE_ID],
            "related_clue_ids": [CLUE_ID],
        }
    ]
    assert populated_store.load_cache(f"response:talk_to_npc:{NPC_ID}:ask about the outage") is None


def test_handle_player_request_persists_generated_exit_line_in_npc_memory(
    populated_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lantern_city import engine

    request = make_request(
        intent="conversation",
        target_id=NPC_ID,
        input_text="Ask what the clerk was afraid of.",
    )

    monkeypatch.setattr(
        engine,
        "_generate_npc_dialogue",
        lambda *args, **kwargs: NPCResponseGenerationResult.model_validate(
            {
                "task_type": "npc_response",
                "request_id": request.id,
                "summary_text": "Ila answers carefully, then closes the thread.",
                "structured_updates": {
                    "dialogue_act": "answer_then_close",
                    "npc_stance": "guarded",
                    "relationship_shift": {
                        "trust_delta": 0.0,
                        "suspicion_delta": 0.0,
                        "fear_delta": 0.0,
                        "tag": "steady",
                    },
                    "clue_effects": [],
                    "access_effects": [],
                    "redirect_targets": [],
                },
                "cacheable_text": {
                    "npc_line": "He was afraid of how quickly a correction could become an erasure.",
                    "follow_up_suggestions": ["Ask who could authorize the erasure."],
                    "exit_line_if_needed": "That is all I can risk saying while the lamps are still watching.",
                },
                "confidence": 0.8,
                "warnings": [],
            }
        ),
    )

    outcome = engine.handle_player_request(populated_store, city_id=CITY_ID, request=request)
    npc = populated_store.load_object("NPCState", NPC_ID)

    assert outcome.response.narrative_text == "He was afraid of how quickly a correction could become an erasure."
    assert isinstance(npc, NPCState)
    assert npc.memory_log[-1]["memory_type"] == "conversation"
    assert npc.memory_log[-1]["turn"] == TURN_ONE
    assert npc.memory_log[-1]["npc_exit_line"] == (
        "That is all I can risk saying while the lamps are still watching."
    )
    assert npc.memory_log[-1]["dialogue_act"] == "answer_then_close"
    assert npc.memory_log[-1]["npc_stance"] == "guarded"
    assert npc.memory_log[-1]["relationship_tag"] == "steady"
    assert npc.memory_log[-1]["summary_text"] == "Ila answers carefully, then closes the thread."


def test_handle_player_request_biases_records_pressure_into_redirects_and_paper_trails(
    populated_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lantern_city import engine

    city = populated_store.load_object("CityState", CITY_ID)
    npc = populated_store.load_object("NPCState", NPC_ID)
    assert isinstance(city, CityState)
    assert isinstance(npc, NPCState)
    populated_store.save_objects_atomically(
        [
            city.model_copy(update={"faction_ids": ["faction_memory_keepers"]}),
            npc.model_copy(update={"loyalty": "faction_memory_keepers"}),
            FactionState(
                id="faction_memory_keepers",
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                name="Memory Keepers",
                public_goal="preserve continuity",
                hidden_goal="control what the city remembers",
                known_assets=["records", "certification"],
                active_plans=["procedural delay"],
            ),
        ]
    )

    request = make_request(intent="conversation", target_id=NPC_ID, input_text="Ask who changed the ledger.")
    monkeypatch.setattr(
        engine,
        "_generate_npc_dialogue",
        lambda *args, **kwargs: NPCResponseGenerationResult.model_validate(
            {
                "task_type": "npc_response",
                "request_id": request.id,
                "summary_text": "Ila redirects you toward the annex record trail.",
                "structured_updates": {
                    "dialogue_act": "redirect_with_hint",
                    "npc_stance": "careful and guarded",
                    "relationship_shift": {
                        "trust_delta": 0.0,
                        "suspicion_delta": 0.0,
                        "fear_delta": 0.0,
                        "tag": "steady",
                    },
                    "clue_effects": [],
                    "access_effects": [
                        {
                            "effect_type": "soft_unlock",
                            "target_id": "location_shrine_lane",
                            "note": "The record trail bends back through Shrine Lane.",
                        }
                    ],
                    "redirect_targets": [
                        {
                            "target_type": "location",
                            "target_id": "location_shrine_lane",
                            "reason": "The annex corrections route through Shrine Lane.",
                        }
                    ],
                },
                "cacheable_text": {
                    "npc_line": "If you want the correction, follow where the page was allowed to pass.",
                    "follow_up_suggestions": ["Ask who certified the change."],
                    "exit_line_if_needed": "That is all the record will tolerate from me.",
                },
                "confidence": 0.8,
                "warnings": [],
            }
        ),
    )

    outcome = engine.handle_player_request(populated_store, city_id=CITY_ID, request=request)

    assert "Follow the redirected paper trail to Shrine Lane" in outcome.response.now_available
    assert "Check the record trail at Shrine Lane" in outcome.response.now_available
    assert "Ask who certified the change." in outcome.response.next_actions
    assert "The record trail bends back through Shrine Lane." in outcome.response.learned
    assert any("reply favored omission, deflection, and paper trails" in line for line in outcome.response.state_changes)


def test_handle_player_request_biases_civic_pressure_into_formal_routing(
    populated_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lantern_city import engine

    city = populated_store.load_object("CityState", CITY_ID)
    npc = populated_store.load_object("NPCState", NPC_ID)
    assert isinstance(city, CityState)
    assert isinstance(npc, NPCState)
    populated_store.save_objects_atomically(
        [
            city.model_copy(update={"faction_ids": ["faction_council_lights"]}),
            npc.model_copy(update={"loyalty": "faction_council_lights"}),
            FactionState(
                id="faction_council_lights",
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                name="Council of Lights",
                public_goal="maintain public order",
                hidden_goal="monopolize lantern legitimacy",
                known_assets=["compliance", "access permits"],
                active_plans=["official review"],
            ),
        ]
    )

    request = make_request(intent="conversation", target_id=NPC_ID, input_text="Ask to enter the ward office.")
    monkeypatch.setattr(
        engine,
        "_generate_npc_dialogue",
        lambda *args, **kwargs: NPCResponseGenerationResult.model_validate(
            {
                "task_type": "npc_response",
                "request_id": request.id,
                "summary_text": "Ila routes you through official channels.",
                "structured_updates": {
                    "dialogue_act": "formal_refusal_with_route",
                    "npc_stance": "official and guarded",
                    "relationship_shift": {
                        "trust_delta": 0.0,
                        "suspicion_delta": 0.0,
                        "fear_delta": 0.0,
                        "tag": "steady",
                    },
                    "clue_effects": [],
                    "access_effects": [
                        {
                            "effect_type": "soft_unlock",
                            "target_id": "location_shrine_lane",
                            "note": "Requests have to be logged through Shrine Lane first.",
                        }
                    ],
                    "redirect_targets": [],
                },
                "cacheable_text": {
                    "npc_line": "You can file the request, but it goes through the proper desk first.",
                    "follow_up_suggestions": ["Ask for the proper desk."],
                    "exit_line_if_needed": "That is the process.",
                },
                "confidence": 0.8,
                "warnings": [],
            }
        ),
    )

    outcome = engine.handle_player_request(populated_store, city_id=CITY_ID, request=request)

    assert "Request official access to Shrine Lane" in outcome.response.now_available
    assert "Make a formal request: Ask for the proper desk." in outcome.response.next_actions
    assert "Requests have to be logged through Shrine Lane first." in outcome.response.learned
    assert any("reply stayed procedural and access-minded" in line for line in outcome.response.state_changes)


def test_handle_player_request_returns_inspection_response_without_state_changes(
    populated_store: SQLiteStore,
) -> None:
    from lantern_city.engine import handle_player_request

    request = make_request(intent="inspect location", target_id=LOCATION_ID)

    outcome = handle_player_request(populated_store, city_id=CITY_ID, request=request)
    city = populated_store.load_object("CityState", CITY_ID)
    location = populated_store.load_object("LocationState", LOCATION_ID)

    assert outcome.intent == "inspect_location"
    assert outcome.changed_objects == []
    assert (
        outcome.response.narrative_text == "You inspect Shrine Lane for anything that stands out."
    )
    assert outcome.response.learned == ["Fresh scoring marks suggest recent tampering."]
    assert outcome.response.now_available == ["Ask about what you found"]
    assert outcome.response.next_actions == ["Inspect a narrower detail", "Review known clues"]
    assert city is not None
    assert isinstance(city, CityState)
    assert city.version == 1
    assert location is not None
    assert isinstance(location, LocationState)
    assert location.version == 1


def test_handle_player_request_returns_case_progression_response_without_state_changes(
    populated_store: SQLiteStore,
) -> None:
    from lantern_city.engine import handle_player_request

    request = make_request(intent="review case", target_id=CASE_ID)

    outcome = handle_player_request(populated_store, city_id=CITY_ID, request=request)
    case = populated_store.load_object("CaseState", CASE_ID)

    assert outcome.intent == "case_progression"
    assert outcome.changed_objects == []
    assert outcome.response.narrative_text == "You review The Missing Clerk."
    assert outcome.response.learned == []
    assert outcome.response.now_available == ["Follow a case lead"]
    assert outcome.response.next_actions == ["Inspect related evidence", "Speak to an involved NPC"]
    assert case is not None
    assert isinstance(case, CaseState)
    assert case.version == 1


def test_handle_player_request_flags_pre_case_clue_as_significant_during_conversation(
    populated_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lantern_city import engine

    request = make_request(
        intent="conversation",
        target_id=NPC_ID,
        input_text="Ask what seems wrong here.",
    )
    pre_case_slice = replace(_district_entry_slice(request), case=None)

    monkeypatch.setattr(
        engine,
        "orchestrate_request",
        lambda store, *, city_id, request: OrchestratedRequest(
            request=request,
            intent="talk_to_npc",
            active_slice=pre_case_slice,
        ),
    )

    outcome = engine.handle_player_request(populated_store, city_id=CITY_ID, request=request)

    assert outcome.response.learned == ["Notable clue: Fresh scoring marks suggest recent tampering."]
    assert outcome.response.case_relevance == [
        "New lead: This clue feels significant, even though you do not yet know what case it belongs to.",
        "Clue reliability: unknown",
        "Lantern condition: dim",
    ]


def test_handle_player_request_flags_pre_case_clue_as_significant_during_inspection(
    populated_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lantern_city import engine

    request = make_request(intent="inspect location", target_id=LOCATION_ID)
    pre_case_slice = replace(_district_entry_slice(request), case=None, location=LocationState(
        id=LOCATION_ID,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        district_id=DISTRICT_ID,
        name="Shrine Lane",
        location_type="shrine",
        known_npc_ids=[NPC_ID],
        clue_ids=[CLUE_ID],
    ))

    monkeypatch.setattr(
        engine,
        "orchestrate_request",
        lambda store, *, city_id, request: OrchestratedRequest(
            request=request,
            intent="inspect_location",
            active_slice=pre_case_slice,
        ),
    )

    outcome = engine.handle_player_request(populated_store, city_id=CITY_ID, request=request)

    assert outcome.response.learned == ["Notable clue: Fresh scoring marks suggest recent tampering."]
    assert outcome.response.case_relevance == [
        "New lead: This clue feels significant, even though you do not yet know what case it belongs to.",
        "Clue reliability: unknown",
        "Lantern condition: dim",
    ]


def test_handle_player_request_returns_generic_action_response_without_state_changes(
    populated_store: SQLiteStore,
) -> None:
    from lantern_city.engine import handle_player_request

    request = make_request(intent="wait")

    outcome = handle_player_request(populated_store, city_id=CITY_ID, request=request)
    city = populated_store.load_object("CityState", CITY_ID)

    assert outcome.intent == "generic_action"
    assert outcome.changed_objects == []
    assert outcome.response.narrative_text == "You pause and take stock of the scene."
    assert outcome.response.state_changes == []
    assert outcome.response.learned == []
    assert outcome.response.now_available == []
    assert outcome.response.next_actions == [
        "Review what stands out",
        "Choose a more specific action",
    ]
    assert city is not None
    assert isinstance(city, CityState)
    assert city.version == 1


def test_handle_player_request_raises_when_npc_conversation_slice_has_no_npc(
    populated_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lantern_city import engine

    request = make_request(intent="conversation", target_id=NPC_ID)
    empty_npc_slice = replace(_district_entry_slice(request), npcs=[])

    monkeypatch.setattr(
        engine,
        "orchestrate_request",
        lambda store, *, city_id, request: OrchestratedRequest(
            request=request,
            intent="talk_to_npc",
            active_slice=empty_npc_slice,
        ),
    )

    with pytest.raises(LookupError, match="Conversation request requires an active NPC slice"):
        engine.handle_player_request(populated_store, city_id=CITY_ID, request=request)


def test_handle_player_request_raises_when_district_entry_slice_has_no_district(
    populated_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lantern_city import engine

    request = make_request(intent="district entry", target_id=DISTRICT_ID)
    empty_district_slice = replace(_district_entry_slice(request), district=None)

    monkeypatch.setattr(
        engine,
        "orchestrate_request",
        lambda store, *, city_id, request: OrchestratedRequest(
            request=request,
            intent="district_entry",
            active_slice=empty_district_slice,
        ),
    )

    with pytest.raises(LookupError, match="District request requires an active district slice"):
        engine.handle_player_request(populated_store, city_id=CITY_ID, request=request)
