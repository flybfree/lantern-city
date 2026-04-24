from __future__ import annotations

from dataclasses import dataclass

from lantern_city.models import NPCState, RelationshipSnapshot


@dataclass(frozen=True, slots=True)
class SocialUpdateResult:
    npc: NPCState
    state_changes: list[str]


def apply_relationship_shift(
    npc: NPCState,
    *,
    trust_delta: float = 0.0,
    suspicion_delta: float = 0.0,
    fear_delta: float = 0.0,
    tag: str | None = None,
    source_actor_id: str = "player",
    updated_at: str,
) -> SocialUpdateResult:
    trust = _clamp01(npc.trust_in_player + trust_delta)
    suspicion = _clamp01(npc.suspicion + suspicion_delta)
    fear = _clamp01(npc.fear + fear_delta)

    relationship_status = _relationship_status(trust=trust, suspicion=suspicion, fear=fear)
    relationships = dict(npc.relationships)
    relationships[source_actor_id] = RelationshipSnapshot(
        trust=trust,
        suspicion=suspicion,
        fear=fear,
        status=relationship_status,
        last_updated_at=updated_at,
    )

    relationship_flags = _merge_flag(npc.relationship_flags, relationship_status)
    if tag:
        relationship_flags = _merge_flag(relationship_flags, tag)

    state_changes: list[str] = []
    if trust_delta:
        direction = "rose" if trust_delta > 0 else "fell"
        state_changes.append(f"{npc.name}'s trust {direction}.")
    if suspicion_delta:
        direction = "rose" if suspicion_delta > 0 else "fell"
        state_changes.append(f"{npc.name}'s suspicion {direction}.")
    if fear_delta:
        direction = "rose" if fear_delta > 0 else "fell"
        state_changes.append(f"{npc.name}'s fear {direction}.")
    if tag:
        state_changes.append(f"Social signal: {tag}.")

    return SocialUpdateResult(
        npc=npc.model_copy(
            update={
                "trust_in_player": trust,
                "suspicion": suspicion,
                "fear": fear,
                "relationships": relationships,
                "relationship_flags": relationship_flags,
                "updated_at": updated_at,
            }
        ),
        state_changes=state_changes,
    )


def apply_player_flag(npc: NPCState, *, flag: str, updated_at: str) -> NPCState:
    return npc.model_copy(
        update={
            "player_flags": _merge_flag(npc.player_flags, flag),
            "updated_at": updated_at,
        }
    )


def run_offscreen_npc_tick(
    npc: NPCState,
    *,
    visible_location_ids: list[str],
    updated_at: str,
) -> SocialUpdateResult:
    new_state = _derive_offscreen_state(npc)
    new_location_id = npc.location_id

    if visible_location_ids and _can_relocate(npc):
        current_index = 0
        if npc.location_id in visible_location_ids:
            current_index = visible_location_ids.index(npc.location_id)
        step = 1 if new_state in {"circulating", "searching", "obstructing"} else 0
        if step and len(visible_location_ids) > 1:
            new_location_id = visible_location_ids[(current_index + step) % len(visible_location_ids)]

    recent_event = _build_recent_event(npc, new_state, new_location_id)
    updated = npc.model_copy(
        update={
            "offscreen_state": new_state,
            "location_id": new_location_id,
            "recent_events": _append_recent(npc.recent_events, recent_event),
            "updated_at": updated_at,
        }
    )

    state_changes = []
    if new_state != npc.offscreen_state:
        state_changes.append(f"{npc.name} is now {new_state}.")
    if new_location_id != npc.location_id and new_location_id is not None:
        state_changes.append(f"{npc.name} moved to {new_location_id}.")

    return SocialUpdateResult(npc=updated, state_changes=state_changes)


def summarize_relationship(npc: NPCState) -> str:
    return (
        f"trust={npc.trust_in_player:.2f}, "
        f"suspicion={npc.suspicion:.2f}, "
        f"fear={npc.fear:.2f}, "
        f"offscreen_state={npc.offscreen_state}"
    )


def _derive_offscreen_state(npc: NPCState) -> str:
    if npc.fear >= 0.8:
        return "withdrawing"
    if npc.suspicion >= 0.7 and npc.trust_in_player <= 0.2:
        return "hiding"
    if npc.role_category in {"authority", "gatekeeper"} and npc.suspicion >= 0.45:
        return "obstructing"
    if "route-bound" in npc.relationship_flags or "district-bound" in npc.relationship_flags:
        return "circulating"
    if npc.current_objective:
        return "pursuing_objective"
    return "idle"


def _build_recent_event(npc: NPCState, new_state: str, new_location_id: str | None) -> str:
    if new_location_id and new_location_id != npc.location_id:
        return f"{new_state} via {new_location_id}"
    return new_state


def _can_relocate(npc: NPCState) -> bool:
    if "stationary" in npc.relationship_flags:
        return False
    return npc.offscreen_state not in {"hiding", "withdrawing"}


def _relationship_status(*, trust: float, suspicion: float, fear: float) -> str:
    if trust >= 0.65 and suspicion <= 0.35:
        return "trusted"
    if suspicion >= 0.7:
        return "guarded"
    if fear >= 0.7:
        return "afraid"
    if trust <= 0.2:
        return "wary"
    return "tentative"


def _append_recent(events: list[str], event: str, *, keep: int = 6) -> list[str]:
    return [*events, event][-keep:]


def _merge_flag(flags: list[str], flag: str) -> list[str]:
    if flag in flags:
        return flags
    return [*flags, flag]


def _clamp01(value: float) -> float:
    return round(max(0.0, min(value, 1.0)), 3)


__all__ = [
    "SocialUpdateResult",
    "apply_player_flag",
    "apply_relationship_shift",
    "run_offscreen_npc_tick",
    "summarize_relationship",
]
