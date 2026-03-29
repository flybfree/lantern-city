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
_TERMINAL_STATUSES = {"solved", "partially solved", "failed"}
_ALLOWED_TRANSITIONS = {
    "latent": {"active"},
    "active": {"stalled", "escalated", "solved", "partially solved", "failed"},
    "stalled": {"active", "escalated", "partially solved", "failed"},
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
    return case.model_copy(
        update={
            "status": new_status,
            "updated_at": updated_at,
            "resolution_summary": resolution_summary or case.resolution_summary,
            "fallout_summary": fallout_summary or case.fallout_summary,
            "open_questions": open_questions,
        }
    )


def case_fallout_tags(status: str) -> list[str]:
    if status not in CASE_STATUSES:
        raise ValueError(f"Invalid case status: {status}")
    return list(_FALLOUT_TAGS[status])
