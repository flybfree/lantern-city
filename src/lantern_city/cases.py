from __future__ import annotations

from lantern_city.models import CaseState

CASE_STATUSES = (
    "latent",
    "active",
    "stalled",
    "escalated",
    "solved",
    "partially solved",
    "failed",
)
PRESSURE_LEVELS = ("low", "rising", "urgent")
_TERMINAL_STATUSES = {"solved", "partially solved", "failed"}
_ALLOWED_TRANSITIONS = {
    "latent": {"active"},
    "active": {"stalled", "escalated", "solved", "partially solved", "failed"},
    "stalled": {"active", "escalated", "solved", "partially solved", "failed"},
    "escalated": {"active", "solved", "partially solved", "failed"},
    "solved": set(),
    "partially solved": {"solved", "failed"},
    "failed": set(),
}
_FALLOUT_TAGS = {
    "active": ["investigation_open"],
    "stalled": ["blocked_progress", "pressure_builds"],
    "escalated": ["district_pressure", "fallout_expands"],
    "solved": ["city_change", "case_closed"],
    "partially solved": ["stabilized_but_unresolved", "followup_case_likely"],
    "failed": ["consequences_land", "case_closed"],
}


def transition_case(
    case: CaseState,
    new_status: str,
    *,
    updated_at: str,
    resolution_summary: str | None = None,
    fallout_summary: str | None = None,
) -> CaseState:
    if new_status not in CASE_STATUSES:
        raise ValueError(f"Invalid case status: {new_status}")
    if new_status == case.status:
        return case.model_copy(
            update={
                "updated_at": updated_at,
                "fallout_summary": fallout_summary or case.fallout_summary,
            }
        )
    if case.status in _TERMINAL_STATUSES:
        raise ValueError(f"Cannot transition terminal case from {case.status} to {new_status}")
    if new_status not in _ALLOWED_TRANSITIONS[case.status]:
        raise ValueError(f"Cannot transition case from {case.status} to {new_status}")
    if new_status in _TERMINAL_STATUSES and not resolution_summary:
        raise ValueError(f"Transition to {new_status} requires a resolution summary")

    open_questions = [] if new_status == "solved" else list(case.open_questions)
    active_resolution_window = case.active_resolution_window
    if new_status == "latent":
        active_resolution_window = "closed"
    elif new_status in {"active", "stalled", "escalated"}:
        active_resolution_window = "open" if new_status == "active" else "narrowing"
    elif new_status in _TERMINAL_STATUSES:
        active_resolution_window = "closed"
    return case.model_copy(
        update={
            "status": new_status,
            "updated_at": updated_at,
            "resolution_summary": resolution_summary or case.resolution_summary,
            "fallout_summary": fallout_summary or case.fallout_summary,
            "open_questions": open_questions,
            "active_resolution_window": active_resolution_window,
        }
    )


def note_case_progress(
    case: CaseState,
    *,
    updated_at: str,
    reason: str,
) -> CaseState:
    is_last_chance = "failure_warning_issued" in case.offscreen_risk_flags
    next_status = case.status if is_last_chance else ("active" if case.status in {"stalled", "escalated"} else case.status)
    risk_flags = [flag for flag in case.offscreen_risk_flags if flag not in {"stalled_progress"}]
    district_effects = list(case.district_effects)
    progress_note = f"progress:{reason}"
    if progress_note not in district_effects:
        district_effects = [*district_effects, progress_note][-6:]
    return case.model_copy(
        update={
            "status": next_status,
            "pressure_level": case.pressure_level if is_last_chance else ("low" if case.pressure_level == "rising" else case.pressure_level),
            "time_since_last_progress": 0,
            "updated_at": updated_at,
            "offscreen_risk_flags": risk_flags,
            "active_resolution_window": "narrowing" if is_last_chance else "open",
            "district_effects": district_effects,
        }
    )


def advance_case_pressure(case: CaseState, *, updated_at: str) -> tuple[CaseState, list[str]]:
    if case.status in _TERMINAL_STATUSES or case.status == "latent":
        return case, []

    idle_turns = case.time_since_last_progress + 1
    pressure_level = _pressure_for_idle_turns(idle_turns)
    next_status = case.status
    notices: list[str] = []

    if idle_turns >= 2 and case.status == "active":
        next_status = "stalled"
        notices.append(f"{case.title} is stalling.")
    if idle_turns >= 4 and case.status in {"active", "stalled"}:
        next_status = "escalated"
        notices.append(f"{case.title} is escalating.")

    risk_flags = _merge_flag(case.offscreen_risk_flags, "stalled_progress" if idle_turns >= 2 else "")
    if pressure_level == "urgent":
        risk_flags = _merge_flag(risk_flags, "urgent_window")

    district_effects = list(case.district_effects)
    pressure_note = f"pressure:{pressure_level}"
    if pressure_note not in district_effects:
        district_effects = [*district_effects, pressure_note][-6:]

    updated = case.model_copy(
        update={
            "status": next_status,
            "pressure_level": pressure_level,
            "time_since_last_progress": idle_turns,
            "updated_at": updated_at,
            "offscreen_risk_flags": risk_flags,
            "active_resolution_window": "narrowing" if pressure_level != "low" else "open",
            "district_effects": district_effects,
        }
    )

    return updated, notices


def case_pressure_summary(case: CaseState) -> str:
    return (
        f"pressure={case.pressure_level}, "
        f"idle={case.time_since_last_progress}, "
        f"window={case.active_resolution_window}, "
        f"status={case.status}"
    )


def case_fallout_tags(status: str) -> list[str]:
    if status not in CASE_STATUSES:
        raise ValueError(f"Invalid case status: {status}")
    return list(_FALLOUT_TAGS[status])


def _pressure_for_idle_turns(idle_turns: int) -> str:
    if idle_turns >= 4:
        return "urgent"
    if idle_turns >= 2:
        return "rising"
    return "low"


def _merge_flag(flags: list[str], flag: str) -> list[str]:
    if not flag or flag in flags:
        return flags
    return [*flags, flag]
