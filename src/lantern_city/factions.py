from __future__ import annotations

from dataclasses import dataclass

from lantern_city.models import CaseState, CityState, FactionState


@dataclass(frozen=True, slots=True)
class FactionTurnResult:
    faction: FactionState
    notices: list[str]


_ATTITUDE_ORDER = ("neutral", "wary", "guarded", "hostile")


def run_faction_turn(
    faction: FactionState,
    *,
    city: CityState,
    related_cases: list[CaseState],
    updated_at: str,
    focus_district_id: str | None = None,
) -> FactionTurnResult:
    notices: list[str] = []
    district_id = _target_district(faction, focus_district_id)
    active_plans = list(faction.active_plans)
    attitude = faction.attitude_toward_player

    if district_id is not None and city.player_presence_level >= 0.1:
        plan = f"contain scrutiny in {district_id}"
        if plan not in active_plans:
            active_plans = [plan, *active_plans][:4]
            notices.append(f"{faction.name} is tightening its posture in {district_id}.")
        if faction.influence_by_district.get(district_id, 0.0) >= 0.5:
            next_attitude = _escalate_attitude(attitude)
            if next_attitude != attitude:
                attitude = next_attitude
                notices.append(f"{faction.name} is now {attitude} toward you.")

    if related_cases:
        hottest_case = sorted(
            related_cases,
            key=lambda case: (case.pressure_level, case.time_since_last_progress),
        )[-1]
        pressure_plan = f"manage {hottest_case.title.lower()} fallout"
        if pressure_plan not in active_plans:
            active_plans = [pressure_plan, *active_plans][:4]
            notices.append(f"{faction.name} is moving around {hottest_case.title}.")

    updated = faction.model_copy(
        update={
            "active_plans": active_plans,
            "attitude_toward_player": attitude,
            "updated_at": updated_at,
        }
    )
    return FactionTurnResult(faction=updated, notices=notices)


def _target_district(faction: FactionState, focus_district_id: str | None) -> str | None:
    if focus_district_id is not None and focus_district_id in faction.influence_by_district:
        return focus_district_id
    if not faction.influence_by_district:
        return None
    return max(faction.influence_by_district.items(), key=lambda item: item[1])[0]


def _escalate_attitude(attitude: str) -> str:
    if attitude not in _ATTITUDE_ORDER:
        return "wary"
    index = _ATTITUDE_ORDER.index(attitude)
    if index >= len(_ATTITUDE_ORDER) - 1:
        return attitude
    return _ATTITUDE_ORDER[index + 1]


__all__ = ["FactionTurnResult", "run_faction_turn"]
