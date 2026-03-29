from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lantern_city.active_slice import ActiveSlice
from lantern_city.cache import StoreBackedCache
from lantern_city.models import LocationState
from lantern_city.store import SQLiteStore

type JSONDict = dict[str, Any]


@dataclass(frozen=True, slots=True)
class PrecomputePlan:
    cache_key: str
    task_type: str
    target_type: str
    target_id: str
    rationale: str

    def to_payload(self) -> JSONDict:
        return {
            "task_type": self.task_type,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "rationale": self.rationale,
        }


def build_precompute_cache_key(*, city_id: str, focus_id: str | None) -> str:
    return ":".join(["background", city_id, focus_id or "city", "next_step"])


def plan_next_precompute(store: SQLiteStore, active_slice: ActiveSlice) -> PrecomputePlan | None:
    district = active_slice.district
    if district is None:
        return None
    if active_slice.location is not None:
        return None
    if not district.visible_locations:
        return None

    first_location_id = district.visible_locations[0]
    location = store.load_object("LocationState", first_location_id)
    if not isinstance(location, LocationState):
        return None

    return PrecomputePlan(
        cache_key=build_precompute_cache_key(city_id=active_slice.city.id, focus_id=district.id),
        task_type="inspect_location",
        target_type="LocationState",
        target_id=location.id,
        rationale="first_visible_location",
    )


def store_precompute_plan(
    cache: StoreBackedCache,
    plan: PrecomputePlan,
    *,
    active_slice: ActiveSlice,
    store: SQLiteStore,
) -> None:
    dependencies = [active_slice.city]
    if active_slice.district is not None:
        dependencies.append(active_slice.district)

    target = store.load_object(plan.target_type, plan.target_id)
    if target is not None:
        dependencies.append(target)

    owner = active_slice.district or active_slice.city
    cache.set(
        key=plan.cache_key,
        payload=plan.to_payload(),
        owner=owner,
        dependencies=dependencies,
    )


def load_precompute_plan_payload(cache: StoreBackedCache, cache_key: str) -> JSONDict | None:
    return cache.get(cache_key)


__all__ = [
    "PrecomputePlan",
    "build_precompute_cache_key",
    "load_precompute_plan_payload",
    "plan_next_precompute",
    "store_precompute_plan",
]
