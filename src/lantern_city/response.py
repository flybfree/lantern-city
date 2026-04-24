from __future__ import annotations

from pydantic import Field

from lantern_city.models import LanternCityModel


class ResponsePayload(LanternCityModel):
    narrative_text: str
    state_changes: list[str] = Field(default_factory=list)
    learned: list[str] = Field(default_factory=list)
    visible_npcs: list[str] = Field(default_factory=list)
    notable_objects: list[str] = Field(default_factory=list)
    exits: list[str] = Field(default_factory=list)
    case_relevance: list[str] = Field(default_factory=list)
    now_available: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    text: str


def compose_response(
    *,
    narrative_text: str,
    state_changes: list[str] | None = None,
    learned: list[str] | None = None,
    visible_npcs: list[str] | None = None,
    notable_objects: list[str] | None = None,
    exits: list[str] | None = None,
    case_relevance: list[str] | None = None,
    now_available: list[str] | None = None,
    next_actions: list[str] | None = None,
) -> ResponsePayload:
    resolved_state_changes = state_changes or []
    resolved_learned = learned or []
    resolved_visible_npcs = visible_npcs or []
    resolved_notable_objects = notable_objects or []
    resolved_exits = exits or []
    resolved_case_relevance = case_relevance or []
    resolved_now_available = now_available or []
    resolved_next_actions = next_actions or []

    text = "\n".join(
        [
            f"What happened: {narrative_text}",
            f"What changed: {_format_items(resolved_state_changes)}",
            f"What you learned: {_format_items(resolved_learned)}",
            f"Who matters here: {_format_items(resolved_visible_npcs)}",
            f"What stands out: {_format_items(resolved_notable_objects)}",
            f"Exits and routes: {_format_items(resolved_exits)}",
            f"Case relevance: {_format_items(resolved_case_relevance)}",
            f"Now available: {_format_items(resolved_now_available)}",
            f"Next actions: {_format_items(resolved_next_actions)}",
        ]
    )

    return ResponsePayload(
        narrative_text=narrative_text,
        state_changes=resolved_state_changes,
        learned=resolved_learned,
        visible_npcs=resolved_visible_npcs,
        notable_objects=resolved_notable_objects,
        exits=resolved_exits,
        case_relevance=resolved_case_relevance,
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
