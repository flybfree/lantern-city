from __future__ import annotations

import pytest

from lantern_city.cases import CASE_STATUSES, case_fallout_tags, transition_case
from lantern_city.models import CaseState

TURN_ZERO = "turn_0"
TURN_ONE = "turn_1"


@pytest.fixture
def active_case() -> CaseState:
    return CaseState(
        id="case_01",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
        title="The Missing Clerk",
        case_type="missing person",
        status="active",
        involved_district_ids=["district_old_quarter"],
        involved_npc_ids=["npc_clerk", "npc_keeper"],
        known_clue_ids=["clue_01"],
        open_questions=["Who hid the clerk from the public ledger?"],
        objective_summary="Recover the clerk and explain the ledger tampering.",
    )


def test_case_statuses_include_documented_states() -> None:
    assert set(CASE_STATUSES) == {
        "latent",
        "active",
        "stalled",
        "escalated",
        "solved",
        "partially solved",
        "failed",
    }


def test_transition_case_to_escalated_preserves_open_questions_and_sets_fallout(
    active_case: CaseState,
) -> None:
    updated = transition_case(
        active_case,
        "escalated",
        updated_at=TURN_ONE,
        fallout_summary="District rumors harden into panic after a second outage.",
    )

    assert updated.status == "escalated"
    assert updated.fallout_summary == "District rumors harden into panic after a second outage."
    assert updated.open_questions == active_case.open_questions
    assert "district_pressure" in case_fallout_tags(updated.status)


def test_transition_case_to_solved_requires_resolution_and_closes_questions(
    active_case: CaseState,
) -> None:
    updated = transition_case(
        active_case,
        "solved",
        updated_at=TURN_ONE,
        resolution_summary="The keeper altered archive lanterns to hide the clerk in the cellar.",
        fallout_summary="Archive procedures tighten, but the clerk is restored to the rolls.",
    )

    assert updated.status == "solved"
    assert updated.resolution_summary.startswith("The keeper altered")
    assert updated.open_questions == []
    assert "city_change" in case_fallout_tags(updated.status)


def test_transition_case_rejects_invalid_or_terminal_backtracking(active_case: CaseState) -> None:
    with pytest.raises(ValueError, match="Invalid case status"):
        transition_case(active_case, "obsolete", updated_at=TURN_ONE)

    solved = transition_case(
        active_case,
        "solved",
        updated_at=TURN_ONE,
        resolution_summary="The truth is public.",
    )

    with pytest.raises(ValueError, match="terminal"):
        transition_case(solved, "active", updated_at=TURN_ONE)
