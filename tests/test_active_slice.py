from __future__ import annotations

import pytest

from lantern_city.active_slice import ActiveSlice, MissingWorldObjectError, build_active_slice
from lantern_city.models import (
    CaseState,
    CityState,
    ClueState,
    DistrictState,
    LocationState,
    NPCState,
    PlayerRequest,
    SceneState,
)
from lantern_city.store import SQLiteStore

TURN_ZERO = "turn_0"
CITY_ID = "city_001"
DISTRICT_OLD = "district_old_quarter"
DISTRICT_WARD = "district_lantern_ward"
LOCATION_SHRINE = "location_shrine_lane"
LOCATION_ARCHIVE = "location_archive_steps"
LOCATION_PLAZA = "location_civic_plaza"
NPC_KEEPER = "npc_shrine_keeper"
NPC_CLERK = "npc_archive_clerk"
NPC_GUARD = "npc_ward_guard"
CASE_MAIN = "case_missing_clerk"
CASE_OTHER = "case_lantern_sabotage"
SCENE_TALK = "scene_shrine_conversation"
CLUE_BRACKET = "clue_bracket_marks"
CLUE_LEDGER = "clue_edited_ledger"
CLUE_BADGE = "clue_guard_badge"


def make_request(
    *,
    intent: str,
    target_id: str | None = None,
    location_id: str | None = None,
    case_id: str | None = None,
    scene_id: str | None = None,
    context_refs: dict[str, object] | None = None,
) -> PlayerRequest:
    return PlayerRequest(
        id=f"request_{intent.replace(' ', '_')}",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        player_id="player_001",
        intent=intent,
        target_id=target_id,
        location_id=location_id,
        case_id=case_id,
        scene_id=scene_id,
        context_refs=context_refs or {},
    )


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
                active_case_ids=[CASE_MAIN, CASE_OTHER],
                district_ids=[DISTRICT_OLD, DISTRICT_WARD],
                faction_ids=[],
            ),
            DistrictState(
                id=DISTRICT_OLD,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                name="Old Quarter",
                tone="wet and watchful",
                relevant_npc_ids=[NPC_CLERK, NPC_KEEPER],
                visible_locations=[LOCATION_ARCHIVE, LOCATION_SHRINE],
            ),
            DistrictState(
                id=DISTRICT_WARD,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                name="Lantern Ward",
                tone="bright and disciplined",
                relevant_npc_ids=[NPC_GUARD],
                visible_locations=[LOCATION_PLAZA],
            ),
            LocationState(
                id=LOCATION_SHRINE,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                district_id=DISTRICT_OLD,
                name="Shrine Lane",
                location_type="shrine",
                known_npc_ids=[NPC_KEEPER],
                clue_ids=[CLUE_BRACKET],
            ),
            LocationState(
                id=LOCATION_ARCHIVE,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                district_id=DISTRICT_OLD,
                name="Archive Steps",
                location_type="archive",
                known_npc_ids=[NPC_CLERK],
                clue_ids=[CLUE_LEDGER],
            ),
            LocationState(
                id=LOCATION_PLAZA,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                district_id=DISTRICT_WARD,
                name="Civic Plaza",
                location_type="plaza",
                known_npc_ids=[NPC_GUARD],
                clue_ids=[CLUE_BADGE],
            ),
            NPCState(
                id=NPC_KEEPER,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                name="Ila Venn",
                role_category="informant",
                district_id=DISTRICT_OLD,
                location_id=LOCATION_SHRINE,
                known_clue_ids=[CLUE_BRACKET],
            ),
            NPCState(
                id=NPC_CLERK,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                name="Sered Marr",
                role_category="witness",
                district_id=DISTRICT_OLD,
                location_id=LOCATION_ARCHIVE,
                known_clue_ids=[CLUE_LEDGER],
            ),
            NPCState(
                id=NPC_GUARD,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                name="Tovin Dace",
                role_category="guard",
                district_id=DISTRICT_WARD,
                location_id=LOCATION_PLAZA,
                known_clue_ids=[CLUE_BADGE],
            ),
            CaseState(
                id=CASE_MAIN,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                title="The Missing Clerk",
                case_type="missing person",
                status="active",
                involved_district_ids=[DISTRICT_OLD],
                involved_npc_ids=[NPC_KEEPER, NPC_CLERK],
                known_clue_ids=[CLUE_BRACKET, CLUE_LEDGER],
            ),
            CaseState(
                id=CASE_OTHER,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                title="Lantern Sabotage",
                case_type="sabotage",
                status="active",
                involved_district_ids=[DISTRICT_WARD],
                involved_npc_ids=[NPC_GUARD],
                known_clue_ids=[CLUE_BADGE],
            ),
            SceneState(
                id=SCENE_TALK,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                case_id=CASE_MAIN,
                scene_type="conversation",
                location_id=LOCATION_SHRINE,
                participating_npc_ids=[NPC_KEEPER],
                scene_clue_ids=[CLUE_BRACKET],
            ),
            ClueState(
                id=CLUE_BRACKET,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                source_type="location",
                source_id=LOCATION_SHRINE,
                clue_text="Fresh scoring marks on the bracket.",
                related_npc_ids=[NPC_KEEPER],
                related_case_ids=[CASE_MAIN],
                related_district_ids=[DISTRICT_OLD],
            ),
            ClueState(
                id=CLUE_LEDGER,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                source_type="record",
                source_id=LOCATION_ARCHIVE,
                clue_text="A ledger page has been quietly amended.",
                related_npc_ids=[NPC_CLERK],
                related_case_ids=[CASE_MAIN],
                related_district_ids=[DISTRICT_OLD],
            ),
            ClueState(
                id=CLUE_BADGE,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                source_type="npc",
                source_id=NPC_GUARD,
                clue_text="A civic badge bears fresh soot.",
                related_npc_ids=[NPC_GUARD],
                related_case_ids=[CASE_OTHER],
                related_district_ids=[DISTRICT_WARD],
            ),
        ]
    )
    return store


def test_build_active_slice_for_district_entry(populated_store: SQLiteStore) -> None:
    request = make_request(intent="district entry", target_id=DISTRICT_OLD)

    active_slice = build_active_slice(populated_store, city_id=CITY_ID, request=request)

    assert isinstance(active_slice, ActiveSlice)
    assert active_slice.district is not None
    assert active_slice.district.id == DISTRICT_OLD
    assert active_slice.location is None
    assert active_slice.scene is None
    assert active_slice.case is not None
    assert active_slice.case.id == CASE_MAIN
    assert [npc.id for npc in active_slice.npcs] == [NPC_CLERK, NPC_KEEPER]
    assert [clue.id for clue in active_slice.clues] == [CLUE_BRACKET, CLUE_LEDGER]


def test_build_active_slice_for_npc_conversation(populated_store: SQLiteStore) -> None:
    request = make_request(intent="talk to NPC", target_id=NPC_KEEPER, scene_id=SCENE_TALK)

    active_slice = build_active_slice(populated_store, city_id=CITY_ID, request=request)

    assert active_slice.district is not None
    assert active_slice.district.id == DISTRICT_OLD
    assert active_slice.location is not None
    assert active_slice.location.id == LOCATION_SHRINE
    assert active_slice.scene is not None
    assert active_slice.scene.id == SCENE_TALK
    assert active_slice.case is not None
    assert active_slice.case.id == CASE_MAIN
    assert [npc.id for npc in active_slice.npcs] == [NPC_KEEPER]
    assert [clue.id for clue in active_slice.clues] == [CLUE_BRACKET]


def test_build_active_slice_for_location_inspection(populated_store: SQLiteStore) -> None:
    request = make_request(intent="inspect location", location_id=LOCATION_SHRINE)

    active_slice = build_active_slice(populated_store, city_id=CITY_ID, request=request)

    assert active_slice.district is not None
    assert active_slice.district.id == DISTRICT_OLD
    assert active_slice.location is not None
    assert active_slice.location.id == LOCATION_SHRINE
    assert active_slice.scene is None
    assert active_slice.case is not None
    assert active_slice.case.id == CASE_MAIN
    assert [npc.id for npc in active_slice.npcs] == [NPC_KEEPER]
    assert [clue.id for clue in active_slice.clues] == [CLUE_BRACKET]


def test_build_active_slice_for_case_progression_uses_target_id_as_case_reference(
    populated_store: SQLiteStore,
) -> None:
    request = make_request(intent="case progression", target_id=CASE_MAIN)

    active_slice = build_active_slice(populated_store, city_id=CITY_ID, request=request)

    assert active_slice.district is None
    assert active_slice.location is None
    assert active_slice.scene is None
    assert active_slice.case is not None
    assert active_slice.case.id == CASE_MAIN
    assert active_slice.working_set.case_id == CASE_MAIN
    assert active_slice.working_set.district_id is None
    assert active_slice.npcs == []
    assert [clue.id for clue in active_slice.clues] == [CLUE_BRACKET, CLUE_LEDGER]


def test_build_active_slice_resolves_explicit_location_target_type_without_prefix_rules(
    populated_store: SQLiteStore,
) -> None:
    request = make_request(
        intent="wait",
        target_id=LOCATION_SHRINE,
        context_refs={"target_type": "location"},
    )

    active_slice = build_active_slice(populated_store, city_id=CITY_ID, request=request)

    assert active_slice.location is not None
    assert active_slice.location.id == LOCATION_SHRINE
    assert active_slice.district is not None
    assert active_slice.district.id == DISTRICT_OLD
    assert active_slice.case is not None
    assert active_slice.case.id == CASE_MAIN
    assert active_slice.npcs == []
    assert [clue.id for clue in active_slice.clues] == [CLUE_BRACKET]


def test_build_active_slice_excludes_unrelated_world_objects(populated_store: SQLiteStore) -> None:
    request = make_request(intent="talk to NPC", target_id=NPC_KEEPER, scene_id=SCENE_TALK)

    active_slice = build_active_slice(populated_store, city_id=CITY_ID, request=request)

    assert active_slice.district is not None
    assert active_slice.district.id != DISTRICT_WARD
    assert active_slice.case is not None
    assert active_slice.case.id != CASE_OTHER
    assert {npc.id for npc in active_slice.npcs} == {NPC_KEEPER}
    assert {clue.id for clue in active_slice.clues} == {CLUE_BRACKET}


def test_build_active_slice_raises_clear_error_for_missing_required_reference(
    populated_store: SQLiteStore,
) -> None:
    request = make_request(intent="talk to NPC", target_id="npc_missing")

    with pytest.raises(MissingWorldObjectError, match="NPCState:npc_missing"):
        build_active_slice(populated_store, city_id=CITY_ID, request=request)


def test_build_active_slice_returns_controlled_empty_slice_for_generic_action_without_context(
    populated_store: SQLiteStore,
) -> None:
    request = make_request(intent="wait")

    active_slice = build_active_slice(populated_store, city_id=CITY_ID, request=request)

    assert active_slice.district is None
    assert active_slice.location is None
    assert active_slice.scene is None
    assert active_slice.case is None
    assert active_slice.npcs == []
    assert active_slice.clues == []
    assert active_slice.working_set.city_id == CITY_ID
    assert active_slice.working_set.npc_ids == []
    assert active_slice.working_set.clue_ids == []
