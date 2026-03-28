from __future__ import annotations

import pytest

from lantern_city.progression import (
    DEFAULT_STARTING_SCORES,
    LEARNING_TRACKS,
    apply_progress_change,
    can_convert_clues_to_leverage,
    can_interpret_lantern_clue,
    can_pursue_city_impact_opportunity,
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


def test_lantern_understanding_gates_uncertain_and_distorted_clue_interpretation() -> None:
    novice = starting_progress_state(
        progress_id="progress_novice",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
    )
    expert, _ = apply_progress_change(
        novice,
        track="lantern_understanding",
        amount=50,
        reason="Studied lantern failure patterns across districts.",
        updated_at=TURN_ONE,
    )

    assert can_interpret_lantern_clue(novice, clue_reliability="credible") is True
    assert can_interpret_lantern_clue(novice, clue_reliability="uncertain") is False
    assert can_interpret_lantern_clue(expert, clue_reliability="uncertain") is True
    assert can_interpret_lantern_clue(expert, clue_reliability="distorted") is True


def test_clue_mastery_and_access_gate_leverage_conversion() -> None:
    progress = starting_progress_state(
        progress_id="progress_04",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
    )

    assert can_convert_clues_to_leverage(
        progress,
        contradiction_count=2,
        target_kind="institution",
    ) is False

    sharper, _ = apply_progress_change(
        progress,
        track="clue_mastery",
        amount=25,
        reason="Built a tighter contradiction chain.",
        updated_at=TURN_ONE,
    )
    connected, _ = apply_progress_change(
        sharper,
        track="access",
        amount=35,
        reason="Gained institutional access to present the case.",
        updated_at="turn_2",
    )

    assert can_convert_clues_to_leverage(
        connected,
        contradiction_count=2,
        target_kind="institution",
    ) is True


def test_city_impact_opportunities_require_matching_access_for_larger_scopes() -> None:
    progress = starting_progress_state(
        progress_id="progress_05",
        created_at=TURN_ZERO,
        updated_at=TURN_ZERO,
    )

    assert can_pursue_city_impact_opportunity(progress, scope="local") is True
    assert can_pursue_city_impact_opportunity(progress, scope="district") is False

    elevated, _ = apply_progress_change(
        progress,
        track="city_impact",
        amount=40,
        reason="Resolved a dispute that now affects the whole district.",
        updated_at=TURN_ONE,
    )
    connected, _ = apply_progress_change(
        elevated,
        track="access",
        amount=40,
        reason="Now has the channels to act on district outcomes.",
        updated_at="turn_2",
    )

    assert can_pursue_city_impact_opportunity(connected, scope="district") is True
    assert can_pursue_city_impact_opportunity(connected, scope="citywide") is False
