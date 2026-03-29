from __future__ import annotations

from lantern_city.active_slice import ActiveSlice
from lantern_city.background import (
    PrecomputePlan,
    build_precompute_cache_key,
    load_precompute_plan_payload,
    plan_next_precompute,
    store_precompute_plan,
)
from lantern_city.cache import StoreBackedCache
from lantern_city.models import ActiveWorkingSet, CityState, DistrictState, LocationState
from lantern_city.store import SQLiteStore

TURN_ZERO = "turn_0"
TURN_ONE = "turn_1"
CITY_ID = "city_001"
DISTRICT_ID = "district_old_quarter"
LOCATION_ONE = "location_shrine_lane"
LOCATION_TWO = "location_archive_steps"


def make_active_slice(*, district_version: int = 1) -> ActiveSlice:
    city = CityState(
        id=CITY_ID,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        city_seed_id="cityseed_001",
        district_ids=[DISTRICT_ID],
        faction_ids=[],
    )
    district = DistrictState(
        id=DISTRICT_ID,
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        version=district_version,
        name="Old Quarter",
        tone="wet and watchful",
        lantern_condition="dim",
        visible_locations=[LOCATION_ONE, LOCATION_TWO],
    )
    working_set = ActiveWorkingSet(
        id="synthetic_active_working_set_city_001_request_001",
        created_at="synthetic_active_slice_request_001",
        updated_at="synthetic_active_slice_request_001",
        city_id=CITY_ID,
        district_id=DISTRICT_ID,
    )
    return ActiveSlice(
        city=city,
        working_set=working_set,
        district=district,
        location=None,
        scene=None,
        npcs=[],
        clues=[],
        case=None,
    )


def populate_store(tmp_path, *, district_version: int = 1) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    store.save_objects_atomically(
        [
            CityState(
                id=CITY_ID,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                city_seed_id="cityseed_001",
                district_ids=[DISTRICT_ID],
                faction_ids=[],
            ),
            DistrictState(
                id=DISTRICT_ID,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO if district_version == 1 else TURN_ONE,
                version=district_version,
                name="Old Quarter",
                tone="wet and watchful",
                lantern_condition="dim",
                visible_locations=[LOCATION_ONE, LOCATION_TWO],
            ),
            LocationState(
                id=LOCATION_ONE,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                district_id=DISTRICT_ID,
                name="Shrine Lane",
                location_type="shrine",
            ),
            LocationState(
                id=LOCATION_TWO,
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                district_id=DISTRICT_ID,
                name="Archive Steps",
                location_type="archive",
            ),
        ]
    )
    return store


def test_build_precompute_cache_key_is_explicit_and_stable() -> None:
    cache_key = build_precompute_cache_key(city_id=CITY_ID, focus_id=DISTRICT_ID)

    assert cache_key == "background:city_001:district_old_quarter:next_step"
    assert build_precompute_cache_key(city_id=CITY_ID, focus_id=DISTRICT_ID) == cache_key


def test_plan_next_precompute_selects_only_one_likely_next_step(tmp_path) -> None:
    store = populate_store(tmp_path)
    active_slice = make_active_slice()

    plan = plan_next_precompute(store, active_slice)

    assert plan == PrecomputePlan(
        cache_key="background:city_001:district_old_quarter:next_step",
        task_type="inspect_location",
        target_type="LocationState",
        target_id=LOCATION_ONE,
        rationale="first_visible_location",
    )


def test_plan_next_precompute_does_not_fan_out_into_multiple_branches(tmp_path) -> None:
    store = populate_store(tmp_path)
    active_slice = make_active_slice()

    plan = plan_next_precompute(store, active_slice)

    assert plan is not None
    assert plan.target_id == LOCATION_ONE
    assert plan.target_id != LOCATION_TWO


def test_stored_precompute_plan_is_easy_to_discard_when_state_changes(tmp_path) -> None:
    store = populate_store(tmp_path)
    active_slice = make_active_slice()
    cache = StoreBackedCache(store)
    plan = plan_next_precompute(store, active_slice)

    assert plan is not None
    store_precompute_plan(cache, plan, active_slice=active_slice, store=store)
    store.save_object(
        DistrictState(
            id=DISTRICT_ID,
            created_at=TURN_ZERO,
            updated_at=TURN_ONE,
            version=2,
            name="Old Quarter",
            tone="crowded and alarmed",
            lantern_condition="failing",
            visible_locations=[LOCATION_ONE, LOCATION_TWO],
        )
    )

    loaded_payload = load_precompute_plan_payload(cache, plan.cache_key)

    assert loaded_payload is None
