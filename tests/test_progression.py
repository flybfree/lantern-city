from __future__ import annotations

import pytest

from lantern_city.progression import (
    DEFAULT_STARTING_SCORES,
    LEARNING_TRACKS,
    apply_progress_change,
    current_unlocks,
    describe_track,
    get_tier,
    get_tier_label,
    starting_progress_state,
)

TURN_ZERO = "turn_0"
TURN_ONE = "turn_1"


def test_starting_progress_state_uses_documented_defaults() -> None:
    progress = starting_progress_state(
        progress_id="progress_01",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
    )

    assert progress.lantern_understanding.score == DEFAULT_STARTING_SCORES["lantern_understanding"]
    assert progress.access.score == DEFAULT_STARTING_SCORES["access"]
    assert progress.clue_mastery.tier == "Competent"


def test_tier_lookup_and_labels_follow_documented_thresholds() -> None:
    assert get_tier(0) == 1
    assert get_tier(19) == 1
    assert get_tier(20) == 2
    assert get_tier(59) == 3
    assert get_tier(80) == 5
    assert get_tier_label("access", 3) == "Trusted"
    assert get_tier_label("city_impact", 5) == "Structural"


def test_apply_progress_change_clamps_scores_and_reports_tier_change() -> None:
    progress = starting_progress_state(
        progress_id="progress_02",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
    )

    updated, change = apply_progress_change(
        progress,
        track="access",
        amount=35,
        reason="Secured standing permission to use the archive service hall.",
        updated_at=TURN_ONE,
    )

    assert updated.access.score == 45
    assert updated.access.tier == "Trusted"
    assert change.old_tier == "Public"
    assert change.new_tier == "Trusted"
    assert change.amount == 35
    assert describe_track(updated, "access").startswith("Access: 45")


def test_learning_tracks_reject_losses_unless_explicitly_allowed() -> None:
    progress = starting_progress_state(
        progress_id="progress_03",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
    )

    with pytest.raises(ValueError, match="stable learning track"):
        apply_progress_change(
            progress,
            track="lantern_understanding",
            amount=-3,
            reason="A temporary setback should not erase understanding by default.",
            updated_at=TURN_ONE,
        )

    assert "lantern_understanding" in LEARNING_TRACKS


def test_current_unlocks_returns_useful_mvp_unlock_text() -> None:
    unlocks = current_unlocks("lantern_understanding", 42)

    assert any("Compare witness reliability by location" in unlock for unlock in unlocks)
    assert any("likely lantern-distorted" in unlock for unlock in unlocks)
