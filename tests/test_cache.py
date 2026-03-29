from __future__ import annotations

from lantern_city.cache import CacheDependency, StoreBackedCache, build_cache_key
from lantern_city.models import CityState, DistrictState
from lantern_city.store import SQLiteStore

TURN_ZERO = "turn_0"
TURN_ONE = "turn_1"
CITY_ID = "city_001"
DISTRICT_ID = "district_old_quarter"


def make_city_state(*, version: int = 1, updated_at: str = TURN_ZERO) -> CityState:
    return CityState(
        id=CITY_ID,
        created_at=TURN_ZERO,
        updated_at=updated_at,
        version=version,
        city_seed_id="cityseed_001",
        district_ids=[DISTRICT_ID],
        faction_ids=[],
    )


def make_district_state(*, version: int = 1, updated_at: str = TURN_ZERO) -> DistrictState:
    return DistrictState(
        id=DISTRICT_ID,
        created_at=TURN_ZERO,
        updated_at=updated_at,
        version=version,
        name="Old Quarter",
        tone="wet and watchful",
        lantern_condition="dim",
    )


def test_build_cache_key_is_explicit_and_stable() -> None:
    cache_key = build_cache_key("generated", "DistrictState", DISTRICT_ID, "entry_summary")

    assert cache_key == "generated:DistrictState:district_old_quarter:entry_summary"
    assert build_cache_key("generated", "DistrictState", DISTRICT_ID, "entry_summary") == cache_key


def test_cache_returns_payload_when_dependency_versions_still_match(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    city = make_city_state()
    district = make_district_state()
    store.save_objects_atomically([city, district])
    cache = StoreBackedCache(store)
    cache_key = build_cache_key("generated", "DistrictState", district.id, "entry_summary")

    cache.set(
        key=cache_key,
        payload={"summary": "The ward smells of oil and rain."},
        owner=district,
        dependencies=[city, district],
    )

    loaded = cache.get(cache_key)

    assert loaded == {"summary": "The ward smells of oil and rain."}


def test_cache_returns_none_and_invalidates_entry_when_tracked_version_changes(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    city = make_city_state()
    district = make_district_state()
    store.save_objects_atomically([city, district])
    cache = StoreBackedCache(store)
    cache_key = build_cache_key("generated", "DistrictState", district.id, "entry_summary")

    cache.set(
        key=cache_key,
        payload={"summary": "The ward smells of oil and rain."},
        owner=district,
        dependencies=[city, district],
    )
    store.save_object(make_district_state(version=2, updated_at=TURN_ONE))

    loaded = cache.get(cache_key)

    assert loaded is None
    assert store.load_cache(cache_key) is None


def test_cache_stores_explicit_dependency_versions_in_payload(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "lantern-city.sqlite3")
    city = make_city_state(version=3)
    district = make_district_state(version=5)
    store.save_objects_atomically([city, district])
    cache = StoreBackedCache(store)
    cache_key = build_cache_key("generated", "DistrictState", district.id, "entry_summary")

    cache.set(
        key=cache_key,
        payload={"summary": "The ward smells of oil and rain."},
        owner=CacheDependency.from_model(district),
        dependencies=[CacheDependency.from_model(city), CacheDependency.from_model(district)],
    )

    stored_entry = store.load_cache(cache_key)

    assert stored_entry is not None
    assert stored_entry["payload"]["dependencies"] == [
        {"object_type": "CityState", "object_id": CITY_ID, "version": 3},
        {"object_type": "DistrictState", "object_id": DISTRICT_ID, "version": 5},
    ]
