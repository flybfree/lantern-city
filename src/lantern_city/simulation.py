from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

IDLE_TIMEOUT_SECONDS = 300
MAX_CATCH_UP_TURNS = 3


@dataclass(frozen=True, slots=True)
class WorldTurnPlan:
    total_turns: int
    catch_up_turns: int
    current_time_iso: str


def turn_label(time_index: int) -> str:
    return f"turn_{time_index}"


def plan_world_turn(
    *,
    current_time_index: int,
    last_meaningful_action_at: str | None,
    now: datetime,
    idle_timeout_seconds: int = IDLE_TIMEOUT_SECONDS,
    max_catch_up_turns: int = MAX_CATCH_UP_TURNS,
) -> WorldTurnPlan:
    catch_up_turns = determine_catch_up_turns(
        last_meaningful_action_at,
        now,
        idle_timeout_seconds=idle_timeout_seconds,
        max_catch_up_turns=max_catch_up_turns,
    )
    del current_time_index  # kept for future expansion and explicit call sites
    return WorldTurnPlan(
        total_turns=1 + catch_up_turns,
        catch_up_turns=catch_up_turns,
        current_time_iso=now.astimezone(UTC).isoformat(),
    )


def determine_catch_up_turns(
    last_meaningful_action_at: str | None,
    now: datetime,
    *,
    idle_timeout_seconds: int = IDLE_TIMEOUT_SECONDS,
    max_catch_up_turns: int = MAX_CATCH_UP_TURNS,
) -> int:
    if not last_meaningful_action_at:
        return 0

    try:
        last_action = datetime.fromisoformat(last_meaningful_action_at)
    except ValueError:
        return 0

    normalized_now = now.astimezone(UTC)
    if last_action.tzinfo is None:
        last_action = last_action.replace(tzinfo=UTC)
    else:
        last_action = last_action.astimezone(UTC)

    elapsed_seconds = (normalized_now - last_action).total_seconds()
    if elapsed_seconds < idle_timeout_seconds:
        return 0

    return min(max_catch_up_turns, int(elapsed_seconds // idle_timeout_seconds))


__all__ = [
    "IDLE_TIMEOUT_SECONDS",
    "MAX_CATCH_UP_TURNS",
    "WorldTurnPlan",
    "determine_catch_up_turns",
    "plan_world_turn",
    "turn_label",
]
