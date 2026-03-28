from __future__ import annotations

from pydantic import Field

from lantern_city.models import LanternCityModel


class ResponsePayload(LanternCityModel):
    narrative_text: str
    state_changes: list[str] = Field(default_factory=list)
    learned: list[str] = Field(default_factory=list)
    now_available: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    text: str


def compose_response(
    *,
    narrative_text: str,
    state_changes: list[str] | None = None,
    learned: list[str] | None = None,
    now_available: list[str] | None = None,
    next_actions: list[str] | None = None,
) -> ResponsePayload:
    resolved_state_changes = state_changes or []
    resolved_learned = learned or []
    resolved_now_available = now_available or []
    resolved_next_actions = next_actions or []

    text = "\n".join(
        [
            f"What happened: {narrative_text}",
            f"What changed: {_format_items(resolved_state_changes)}",
            f"What you learned: {_format_items(resolved_learned)}",
            f"Now available: {_format_items(resolved_now_available)}",
            f"Next actions: {_format_items(resolved_next_actions)}",
        ]
    )

    return ResponsePayload(
        narrative_text=narrative_text,
        state_changes=resolved_state_changes,
        learned=resolved_learned,
        now_available=resolved_now_available,
        next_actions=resolved_next_actions,
        text=text,
    )


def _format_items(items: list[str]) -> str:
    if not items:
        return "None"
    if len(items) == 1:
        return items[0]
    return "; ".join(items)


__all__ = ["ResponsePayload", "compose_response"]
