from __future__ import annotations

from dataclasses import dataclass

from lantern_city.models import CaseState, CityState, FactionState


@dataclass(frozen=True, slots=True)
class FactionOperation:
    kind: str
    faction_id: str
    district_id: str | None = None
    case_id: str | None = None
    npc_id: str | None = None


@dataclass(frozen=True, slots=True)
class FactionTurnResult:
    faction: FactionState
    notices: list[str]
    operations: list[FactionOperation]


_ATTITUDE_ORDER = ("neutral", "wary", "guarded", "hostile")


def run_faction_turn(
    faction: FactionState,
    *,
    city: CityState,
    related_cases: list[CaseState],
    updated_at: str,
    focus_district_id: str | None = None,
    district_access_level: str | None = None,
) -> FactionTurnResult:
    notices: list[str] = []
    operations: list[FactionOperation] = []
    district_id = _target_district(faction, focus_district_id)
    faction_style = _faction_style(faction)
    active_plans = list(faction.active_plans)
    attitude = faction.attitude_toward_player

    if district_id is not None and city.player_presence_level >= 0.1:
        if faction.influence_by_district.get(district_id, 0.0) >= 0.5:
            operations.append(
                FactionOperation(
                    kind=_district_operation_kind(
                        faction_style=faction_style,
                        district_access_level=district_access_level,
                    ),
                    faction_id=faction.id,
                    district_id=district_id,
                )
            )
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
        hottest_case = max(
            related_cases,
            key=lambda case: (_pressure_rank(case), case.time_since_last_progress),
        )
        pressure_plan = f"manage {hottest_case.title.lower()} fallout"
        if pressure_plan not in active_plans:
            active_plans = [pressure_plan, *active_plans][:4]
            notices.append(f"{faction.name} is moving around {hottest_case.title}.")
        operations.append(
            FactionOperation(
                kind=_case_operation_kind(
                    faction_style=faction_style,
                    case=hottest_case,
                ),
                faction_id=faction.id,
                case_id=hottest_case.id,
                district_id=district_id,
            )
        )
        if _should_apply_npc_pressure(hottest_case) and hottest_case.npc_pressure_targets:
            operations.append(
                FactionOperation(
                    kind="npc_pressure",
                    faction_id=faction.id,
                    case_id=hottest_case.id,
                    npc_id=hottest_case.npc_pressure_targets[0],
                )
            )

    updated = faction.model_copy(
        update={
            "active_plans": active_plans,
            "attitude_toward_player": attitude,
            "updated_at": updated_at,
        }
    )
    return FactionTurnResult(faction=updated, notices=notices, operations=operations)


def _target_district(faction: FactionState, focus_district_id: str | None) -> str | None:
    if focus_district_id is not None and focus_district_id in faction.influence_by_district:
        return focus_district_id
    if not faction.influence_by_district:
        return None
    return max(faction.influence_by_district.items(), key=lambda item: item[1])[0]


def _faction_style(faction: FactionState) -> str:
    text = " ".join(
        [
            faction.name,
            faction.public_goal,
            faction.hidden_goal,
            *faction.known_assets,
            *faction.active_plans,
        ]
    ).lower()
    if any(token in text for token in ("records", "memory", "archive", "certification", "continuity")):
        return "records"
    if any(token in text for token in ("order", "compliance", "permit", "civic", "lantern", "public confidence")):
        return "civic"
    return "general"


def faction_style_label(faction: FactionState) -> str:
    style = _faction_style(faction)
    if style == "records":
        return "records control"
    if style == "civic":
        return "civic enforcement"
    return "general pressure"


def faction_tactic_label(faction: FactionState) -> str:
    plan = faction.active_plans[0].lower() if faction.active_plans else ""
    if any(token in plan for token in ("cover", "record", "certification", "delay", "correction")):
        return "burying or correcting records"
    if any(token in plan for token in ("review", "reassurance", "order", "permit", "scrutiny")):
        return "tightening official scrutiny"
    if any(token in plan for token in ("isolation", "witness")):
        return "isolating witnesses"
    if any(token in plan for token in ("fallout", "manage")):
        return "managing fallout"
    return "holding pressure"


def _district_operation_kind(*, faction_style: str, district_access_level: str | None) -> str:
    if faction_style == "records":
        return "district_surveillance" if district_access_level in {"watched", "restricted", "controlled", "sealed"} else "district_pressure"
    if faction_style == "civic":
        return "district_surveillance"
    if district_access_level in {"watched", "restricted", "controlled", "sealed"}:
        return "district_surveillance"
    return "district_pressure"


def _pressure_rank(case: CaseState) -> int:
    if case.pressure_level == "urgent":
        return 3
    if case.pressure_level == "rising":
        return 2
    return 1


def _case_operation_kind(*, faction_style: str, case: CaseState) -> str:
    if _should_apply_npc_pressure(case):
        return "case_isolation" if faction_style != "records" else "case_coverup"
    if faction_style == "records":
        return "case_coverup"
    if faction_style == "civic":
        return "case_isolation" if case.pressure_level == "rising" or case.active_resolution_window == "narrowing" else "case_interference"
    if case.pressure_level == "rising" or case.active_resolution_window == "narrowing":
        return "case_interference"
    return "case_coverup"


def _should_apply_npc_pressure(case: CaseState) -> bool:
    return (
        case.pressure_level == "urgent"
        or case.status in {"stalled", "escalated"}
        or "urgent_window" in case.offscreen_risk_flags
    )


def _escalate_attitude(attitude: str) -> str:
    if attitude not in _ATTITUDE_ORDER:
        return "wary"
    index = _ATTITUDE_ORDER.index(attitude)
    if index >= len(_ATTITUDE_ORDER) - 1:
        return attitude
    return _ATTITUDE_ORDER[index + 1]


__all__ = [
    "FactionOperation",
    "FactionTurnResult",
    "faction_style_label",
    "faction_tactic_label",
    "run_faction_turn",
]
