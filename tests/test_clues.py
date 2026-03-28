from __future__ import annotations

import pytest

from lantern_city.clues import (
    CLUE_RELIABILITY_STATES,
    CLUE_STATUS_STATES,
    clarify_clue,
    contradict_clue,
    create_clue,
    set_clue_status,
)

TURN_ONE = "turn_1"
TURN_TWO = "turn_2"


def test_create_clue_uses_source_baselines_and_defaults() -> None:
    testimony = create_clue(
        clue_id="clue_testimony_01",
        source_type="testimony",
        source_id="npc_witness_01",
        clue_text="The witness swears the lamps went out before the scream.",
        related_case_ids=["case_01"],
        related_district_ids=["district_01"],
        created_at=TURN_ONE,
    )
    physical = create_clue(
        clue_id="clue_physical_01",
        source_type="physical",
        source_id="bracket_mark_01",
        clue_text="Fresh tool marks ring the bracket bolts.",
        created_at=TURN_ONE,
    )

    assert testimony.reliability == "uncertain"
    assert testimony.status == "new"
    assert physical.reliability == "credible"
    assert set(CLUE_RELIABILITY_STATES) >= {
        "solid",
        "credible",
        "uncertain",
        "distorted",
        "contradicted",
        "unstable",
    }
    assert set(CLUE_STATUS_STATES) >= {"new", "confirmed", "contradicted", "obsolete"}


def test_clarify_clue_upgrades_fragile_reliability_and_confirms() -> None:
    clue = create_clue(
        clue_id="clue_02",
        source_type="document",
        source_id="ledger_07",
        clue_text="A page number has been scraped away.",
        reliability="uncertain",
        created_at=TURN_ONE,
    )

    clarified = clarify_clue(
        clue,
        clarification_text="The scrape matches archive tools, not age damage.",
        updated_at=TURN_TWO,
    )

    assert clarified.reliability == "credible"
    assert clarified.status == "confirmed"
    assert "Clarification:" in clarified.clue_text
    assert clarified.updated_at == TURN_TWO


def test_contradict_clue_marks_it_contradicted_without_losing_history() -> None:
    clue = create_clue(
        clue_id="clue_03",
        source_type="testimony",
        source_id="npc_01",
        clue_text="The clerk left through the east gate.",
        reliability="credible",
        created_at=TURN_ONE,
    )

    contradicted = contradict_clue(
        clue,
        contradiction_text=(
            "Gate records and soot patterns place the clerk in the archive cellar instead."
        ),
        updated_at=TURN_TWO,
    )

    assert contradicted.reliability == "contradicted"
    assert contradicted.status == "contradicted"
    assert "Contradiction:" in contradicted.clue_text
    assert "contradicted" in contradicted.tags


def test_set_clue_status_validates_allowed_statuses() -> None:
    clue = create_clue(
        clue_id="clue_04",
        source_type="physical",
        source_id="floor_scoring",
        clue_text="Scoring marks lead behind the stacks.",
        created_at=TURN_ONE,
    )

    obsolete = set_clue_status(clue, "obsolete", updated_at=TURN_TWO)
    assert obsolete.status == "obsolete"

    with pytest.raises(ValueError, match="Invalid clue status"):
        set_clue_status(clue, "solved", updated_at=TURN_TWO)
