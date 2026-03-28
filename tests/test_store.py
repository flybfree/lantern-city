from __future__ import annotations

import sqlite3

from lantern_city.models import CityState, DistrictState
from lantern_city.store import SQLiteStore


def make_city_state(*, version: int = 1, updated_at: str = "turn_0") -> CityState:
    return CityState(
        id="city_001",
        created_at="turn_0",
        updated_at=updated_at,
        version=version,
        city_seed_id="cityseed_001",
        time_index=1,
        global_tension=0.2,
        civic_trust=0.6,
        missingness_pressure=0.35,
        active_case_ids=["case_missing_clerk"],
        district_ids=["district_old_quarter"],
        faction_ids=["faction_memory_keepers"],
        player_presence_level=0.1,
    )


def make_district_state(
    *,
    id: str = "district_old_quarter",
    created_at: str = "turn_0",
    updated_at: str = "turn_0",
    version: int = 1,
) -> DistrictState:
    return DistrictState(
        id=id,
        created_at=created_at,
        updated_at=updated_at,
        version=version,
        name="Old Quarter",
        tone="ancient, damp",
        stability=0.47,
        lantern_condition="dim",
    )


def test_store_initializes_sqlite_schema(tmp_path) -> None:
    db_path = tmp_path / "lantern-city.sqlite3"

    SQLiteStore(db_path)

    connection = sqlite3.connect(db_path)
    try:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        connection.close()

    assert {"world_objects", "cache_entries"}.issubset(table_names)


def test_save_and_load_object_round_trip(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    city_state = make_city_state()

    store.save_object(city_state)
    loaded = store.load_object("CityState", city_state.id)

    assert loaded == city_state


def test_save_object_replaces_existing_record_for_same_id_and_type(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")

    store.save_object(make_city_state())
    updated_city_state = make_city_state(version=2, updated_at="turn_1")
    store.save_object(updated_city_state)

    loaded = store.load_object("CityState", updated_city_state.id)

    assert loaded == updated_city_state
    assert loaded.version == 2
    assert loaded.updated_at == "turn_1"


def test_save_object_preserves_created_at_on_update(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")

    store.save_object(make_city_state())
    store.save_object(
        make_city_state(version=2, updated_at="turn_1").model_copy(
            update={"created_at": "turn_99"}
        )
    )

    loaded = store.load_object("CityState", "city_001")

    assert loaded is not None
    assert loaded.created_at == "turn_0"
    assert loaded.updated_at == "turn_1"


def test_save_object_allows_same_id_for_different_types(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    city_state = make_city_state()
    district_state = make_district_state(id=city_state.id)

    store.save_object(city_state)
    store.save_object(district_state)

    assert store.load_object("CityState", city_state.id) == city_state
    assert store.load_object("DistrictState", district_state.id) == district_state
    assert store.list_objects("CityState") == [city_state]
    assert store.list_objects("DistrictState") == [district_state]


def test_list_objects_filters_by_type_and_returns_models(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    city_state = make_city_state()
    district_state = make_district_state()

    store.save_object(city_state)
    store.save_object(district_state)

    listed = store.list_objects("CityState")

    assert listed == [city_state]


def test_delete_object_removes_saved_object(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    city_state = make_city_state()
    store.save_object(city_state)

    store.delete_object("CityState", city_state.id)

    assert store.load_object("CityState", city_state.id) is None


def test_save_and_load_cache_round_trip(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    payload = {"summary": "The district feels stale and uncertain."}

    store.save_cache(
        "district:district_old_quarter:summary",
        payload,
        version=3,
        object_type="DistrictState",
        object_id="district_old_quarter",
        ttl_seconds=600,
    )

    loaded = store.load_cache("district:district_old_quarter:summary")

    assert loaded is not None
    assert loaded["cache_key"] == "district:district_old_quarter:summary"
    assert loaded["object_type"] == "DistrictState"
    assert loaded["object_id"] == "district_old_quarter"
    assert loaded["version"] == 3
    assert loaded["payload"] == payload
    assert loaded["ttl_seconds"] == 600


def test_save_cache_preserves_created_at_on_update(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    cache_key = "district:district_old_quarter:summary"

    store.save_cache(
        cache_key,
        {"summary": "stale"},
        version=1,
        object_type="DistrictState",
        object_id="district_old_quarter",
        created_at="turn_0",
        updated_at="turn_0",
    )
    store.save_cache(
        cache_key,
        {"summary": "fresh"},
        version=2,
        object_type="DistrictState",
        object_id="district_old_quarter",
        created_at="turn_99",
        updated_at="turn_1",
    )

    loaded = store.load_cache(cache_key)

    assert loaded is not None
    assert loaded["created_at"] == "turn_0"
    assert loaded["updated_at"] == "turn_1"
    assert loaded["version"] == 2
    assert loaded["payload"] == {"summary": "fresh"}


def test_invalidate_cache_by_key_prefix_removes_matching_entries(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    store.save_cache(
        "district:district_old_quarter:summary",
        {"summary": "stale"},
        version=1,
        object_type="DistrictState",
        object_id="district_old_quarter",
    )
    store.save_cache(
        "district:district_old_quarter:scene",
        {"scene": "stale"},
        version=1,
        object_type="DistrictState",
        object_id="district_old_quarter",
    )
    store.save_cache(
        "npc:npc_shrine_keeper:summary",
        {"summary": "keep"},
        version=1,
        object_type="NPCState",
        object_id="npc_shrine_keeper",
    )

    invalidated = store.invalidate_cache_by_key_prefix("district:district_old_quarter")

    assert invalidated == 2
    assert store.load_cache("district:district_old_quarter:summary") is None
    assert store.load_cache("district:district_old_quarter:scene") is None
    assert store.load_cache("npc:npc_shrine_keeper:summary") is not None


def test_invalidate_cache_by_key_prefix_treats_wildcards_as_literal_text(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    wildcard_prefix = "district:%"
    matching_key = "district:%:summary"
    other_key = "district:district_old_quarter:summary"
    store.save_cache(
        matching_key,
        {"summary": "remove me"},
        version=1,
        object_type="DistrictState",
        object_id="district_percent",
    )
    store.save_cache(
        other_key,
        {"summary": "keep me"},
        version=1,
        object_type="DistrictState",
        object_id="district_old_quarter",
    )

    invalidated = store.invalidate_cache_by_key_prefix(wildcard_prefix)

    assert invalidated == 1
    assert store.load_cache(matching_key) is None
    assert store.load_cache(other_key) is not None


def test_invalidate_cache_by_object_id_can_target_multiple_entries(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    store.save_cache(
        "district:district_old_quarter:summary",
        {"summary": "stale"},
        version=1,
        object_type="DistrictState",
        object_id="district_old_quarter",
    )
    store.save_cache(
        "location:district_old_quarter:archive_steps",
        {"summary": "also stale"},
        version=1,
        object_type="LocationState",
        object_id="district_old_quarter",
    )

    invalidated = store.invalidate_cache_by_object_id("district_old_quarter")

    assert invalidated == 2
    assert store.load_cache("district:district_old_quarter:summary") is None
    assert store.load_cache("location:district_old_quarter:archive_steps") is None
