from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lantern_city.simulation import determine_catch_up_turns, plan_world_turn, turn_label


def test_turn_label_uses_city_time_index() -> None:
    assert turn_label(0) == "turn_0"
    assert turn_label(4) == "turn_4"


def test_determine_catch_up_turns_returns_zero_without_prior_action() -> None:
    now = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)

    assert determine_catch_up_turns(None, now) == 0
    assert determine_catch_up_turns("", now) == 0


def test_determine_catch_up_turns_is_bounded_by_idle_threshold_and_cap() -> None:
    now = datetime(2026, 4, 24, 12, 20, tzinfo=UTC)

    assert determine_catch_up_turns(now.isoformat(), now) == 0
    assert determine_catch_up_turns((now - timedelta(minutes=4)).isoformat(), now) == 0
    assert determine_catch_up_turns((now - timedelta(minutes=12)).isoformat(), now) == 2
    assert determine_catch_up_turns((now - timedelta(minutes=40)).isoformat(), now) == 3


def test_plan_world_turn_adds_one_base_turn_plus_catch_up() -> None:
    now = datetime(2026, 4, 24, 12, 20, tzinfo=UTC)

    planned = plan_world_turn(
        current_time_index=1,
        last_meaningful_action_at=(now - timedelta(minutes=12)).isoformat(),
        now=now,
    )

    assert planned.total_turns == 3
    assert planned.catch_up_turns == 2
    assert planned.current_time_iso == now.isoformat()
