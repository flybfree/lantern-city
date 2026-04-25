from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import Field, field_validator

from lantern_city.active_slice import ActiveSlice
from lantern_city.generation.writing_guardrails import (
    COMMON_AVOID_RULES,
    NPC_DIALOGUE_RULES,
    TONE_SYSTEM_BLOCK,
)
from lantern_city.models import FactionState, LanternCityModel, PlayerProgressState, PlayerRequest
from lantern_city.progression import can_pressure_npc, can_use_informal_access


class NPCResponseGenerationError(RuntimeError):
    pass


RELATIONSHIP_DELTA_MIN = -1.0
RELATIONSHIP_DELTA_MAX = 1.0
_UNKNOWN_LOCATION_ID = "location_unknown"


def _require_bounded_text(value: str, *, field_name: str, max_length: int) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    if len(value) > max_length:
        raise ValueError(f"{field_name} must stay under {max_length} characters")
    return value


def _require_prefixed_id(value: str, *, field_name: str, prefix: str, max_length: int) -> str:
    value = _require_bounded_text(value, field_name=field_name, max_length=max_length)
    if not value.startswith(prefix):
        raise ValueError(f"{field_name} must start with {prefix}")
    return value


def _require_single_turn_text(value: str, *, field_name: str, max_length: int) -> str:
    value = _require_bounded_text(value, field_name=field_name, max_length=max_length)
    if "\n" in value or "\r" in value:
        raise ValueError(f"{field_name} must be a single reply turn")
    if re.search(r"(?:^|\s)(?:player|npc|you|detective|investigator):", value, flags=re.IGNORECASE):
        raise ValueError(f"{field_name} must not look like a transcript")
    non_ws = [c for c in value if not c.isspace()]
    alpha_count = sum(1 for c in non_ws if c.isalpha())
    if not non_ws or alpha_count < len(non_ws) * 0.25:
        raise ValueError(f"{field_name} must not be an ellipsis or punctuation-only placeholder")
    return value


@runtime_checkable
class SupportsJSONGeneration(Protocol):
    def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2400,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class RelationshipShift(LanternCityModel):
    trust_delta: float = Field(
        default=0.0,
        ge=RELATIONSHIP_DELTA_MIN,
        le=RELATIONSHIP_DELTA_MAX,
        description="Single-turn trust change, bounded to a narrow per-response range.",
    )
    suspicion_delta: float = Field(
        default=0.0,
        ge=RELATIONSHIP_DELTA_MIN,
        le=RELATIONSHIP_DELTA_MAX,
        description="Single-turn suspicion change, bounded to a narrow per-response range.",
    )
    fear_delta: float = Field(
        default=0.0,
        ge=RELATIONSHIP_DELTA_MIN,
        le=RELATIONSHIP_DELTA_MAX,
        description="Single-turn fear change, bounded to a narrow per-response range.",
    )
    tag: str | None = None

    @field_validator("tag")
    @classmethod
    def _validate_tag(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_bounded_text(value, field_name="tag", max_length=80)


class ClueEffect(LanternCityModel):
    effect_type: str
    clue_id: str | None = None
    note: str

    @field_validator("effect_type")
    @classmethod
    def _validate_effect_type(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="effect_type", max_length=40)

    @field_validator("clue_id")
    @classmethod
    def _validate_clue_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_prefixed_id(value, field_name="clue_id", prefix="clue_", max_length=80)

    @field_validator("note")
    @classmethod
    def _validate_note(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="note", max_length=160)


class AccessEffect(LanternCityModel):
    effect_type: str
    target_id: str | None = None
    note: str

    @field_validator("effect_type")
    @classmethod
    def _validate_effect_type(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="effect_type", max_length=40)

    @field_validator("target_id")
    @classmethod
    def _validate_target_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_prefixed_id(
            value, field_name="target_id", prefix="location_", max_length=80
        )

    @field_validator("note")
    @classmethod
    def _validate_note(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="note", max_length=160)


class RedirectTarget(LanternCityModel):
    target_type: str
    target_id: str
    reason: str

    @field_validator("target_type")
    @classmethod
    def _validate_target_type(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="target_type", max_length=40)

    @field_validator("target_id")
    @classmethod
    def _validate_target_id(cls, value: str) -> str:
        return _require_prefixed_id(
            value, field_name="target_id", prefix="location_", max_length=80
        )

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="reason", max_length=160)


class NPCResponseStructuredUpdates(LanternCityModel):
    dialogue_act: str
    npc_stance: str
    relationship_shift: RelationshipShift
    clue_effects: list[ClueEffect] = Field(default_factory=list, max_length=3)
    access_effects: list[AccessEffect] = Field(default_factory=list, max_length=3)
    redirect_targets: list[RedirectTarget] = Field(default_factory=list, max_length=3)

    @field_validator("dialogue_act")
    @classmethod
    def _validate_dialogue_act(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="dialogue_act", max_length=60)

    @field_validator("npc_stance")
    @classmethod
    def _validate_npc_stance(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="npc_stance", max_length=80)


class NPCResponseCacheableText(LanternCityModel):
    npc_line: str
    follow_up_suggestions: list[str] = Field(min_length=1, max_length=4)
    exit_line_if_needed: str | None = None

    @field_validator("npc_line")
    @classmethod
    def _validate_npc_line(cls, value: str) -> str:
        return _require_single_turn_text(value, field_name="npc_line", max_length=640)

    @field_validator("follow_up_suggestions")
    @classmethod
    def _validate_follow_up_suggestions(cls, value: list[str]) -> list[str]:
        return [
            _require_bounded_text(item, field_name="follow_up_suggestions", max_length=120)
            for item in value
        ]

    @field_validator("exit_line_if_needed")
    @classmethod
    def _validate_exit_line_if_needed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_single_turn_text(value, field_name="exit_line_if_needed", max_length=160)


class NPCResponseGenerationResult(LanternCityModel):
    task_type: Literal["npc_response"] = "npc_response"
    request_id: str
    summary_text: str
    structured_updates: NPCResponseStructuredUpdates
    cacheable_text: NPCResponseCacheableText
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("summary_text")
    @classmethod
    def _validate_summary_text(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="summary_text", max_length=320)

    @field_validator("warnings")
    @classmethod
    def _validate_warnings(cls, value: list[str]) -> list[str]:
        return [
            _require_bounded_text(item, field_name="warnings", max_length=120) for item in value
        ]


def _humanize_loose_effect_text(value: object) -> str:
    text = str(value).strip().replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text[:160] if len(text) > 160 else text


def _normalize_relationship_delta(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(RELATIONSHIP_DELTA_MIN, min(RELATIONSHIP_DELTA_MAX, numeric))


def _normalize_redirect_target(entry: dict[str, Any]) -> dict[str, Any]:
    target_type = entry.get("target_type") or entry.get("type") or "redirect hint"
    target_id = entry.get("target_id") or entry.get("location_id") or entry.get("target")
    if not isinstance(target_id, str) or not target_id.startswith("location_"):
        target_id = _UNKNOWN_LOCATION_ID

    reason_parts = [
        entry.get("reason"),
        entry.get("note"),
        entry.get("focus"),
        entry.get("area"),
    ]
    reason = next(
        (
            _humanize_loose_effect_text(part)
            for part in reason_parts
            if isinstance(part, str) and part.strip()
        ),
        "follow the lead this NPC is pointing toward",
    )

    return {
        "target_type": _humanize_loose_effect_text(target_type),
        "target_id": target_id,
        "reason": reason,
    }


def _normalize_access_effect(entry: dict[str, Any]) -> dict[str, Any]:
    effect_type = entry.get("effect_type") or entry.get("type") or "access hint"
    target_id = entry.get("target_id") or entry.get("location_id")
    if not isinstance(target_id, str) or not target_id.startswith("location_"):
        target_id = None
    note = next(
        (
            _humanize_loose_effect_text(part)
            for part in (entry.get("note"), entry.get("reason"), entry.get("focus"), entry.get("area"))
            if isinstance(part, str) and part.strip()
        ),
        "follow up on the access lead this NPC surfaced",
    )
    return {
        "effect_type": _humanize_loose_effect_text(effect_type),
        "target_id": target_id,
        "note": note,
    }


def _normalize_clue_effect(entry: dict[str, Any]) -> dict[str, Any]:
    effect_type = entry.get("effect_type") or entry.get("type") or "clue hint"
    clue_id = entry.get("clue_id")
    if not isinstance(clue_id, str) or not clue_id.startswith("clue_"):
        clue_id = None
    note = next(
        (
            _humanize_loose_effect_text(part)
            for part in (entry.get("note"), entry.get("reason"), entry.get("focus"), entry.get("detail"))
            if isinstance(part, str) and part.strip()
        ),
        "follow up on the clue this NPC is surfacing",
    )
    return {
        "effect_type": _humanize_loose_effect_text(effect_type),
        "clue_id": clue_id,
        "note": note,
    }


def sanitize_npc_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize near-miss structured outputs from smaller or looser local models.

    Some OpenAI-compatible local models return simple string lists for nested structured
    fields even when asked for json_schema output. Convert those into minimally valid
    object shapes so downstream validation can keep useful responses instead of failing
    outright.
    """
    if payload.get("task_type") != "npc_response":
        payload["task_type"] = "npc_response"

    updates = payload.get("structured_updates")
    if not isinstance(updates, dict):
        return payload

    relationship_shift = updates.get("relationship_shift")
    if isinstance(relationship_shift, dict):
        for field_name in ("trust_delta", "suspicion_delta", "fear_delta"):
            if field_name in relationship_shift:
                relationship_shift[field_name] = _normalize_relationship_delta(
                    relationship_shift[field_name]
                )

    if "redirect_targets" in updates:
        normalized_redirects: list[dict[str, Any]] = []
        for entry in updates["redirect_targets"]:
            if isinstance(entry, str):
                normalized_redirects.append(
                    {
                        "target_type": "redirect hint",
                        "target_id": _UNKNOWN_LOCATION_ID,
                        "reason": _humanize_loose_effect_text(entry),
                    }
                )
            elif isinstance(entry, dict):
                normalized_redirects.append(_normalize_redirect_target(entry))
        updates["redirect_targets"] = normalized_redirects

    if "access_effects" in updates:
        normalized_access: list[dict[str, Any]] = []
        for entry in updates["access_effects"]:
            if isinstance(entry, str):
                normalized_access.append(
                    {
                        "effect_type": "access hint",
                        "target_id": None,
                        "note": _humanize_loose_effect_text(entry),
                    }
                )
            elif isinstance(entry, dict):
                normalized_access.append(_normalize_access_effect(entry))
        updates["access_effects"] = normalized_access

    if "clue_effects" in updates:
        normalized_clues: list[dict[str, Any]] = []
        for entry in updates["clue_effects"]:
            if isinstance(entry, str):
                normalized_clues.append(
                    {
                        "effect_type": "clue hint",
                        "clue_id": None,
                        "note": _humanize_loose_effect_text(entry),
                    }
                )
            elif isinstance(entry, dict):
                normalized_clues.append(_normalize_clue_effect(entry))
        updates["clue_effects"] = normalized_clues

    return payload


@dataclass(frozen=True, slots=True)
class NPCResponseGenerationRequest:
    request_id: str
    active_slice: ActiveSlice
    player_request: PlayerRequest
    npc_id: str | None = None
    progress: PlayerProgressState | None = None
    case_intro_text: str | None = None
    loyalty_faction: FactionState | None = None

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        if not self.active_slice.npcs:
            raise ValueError(
                "npc response generation requires at least one npc in the active slice"
            )
        self._target_npc()

    def _target_npc_id(self) -> str:
        return self.npc_id or self.player_request.target_id or self.active_slice.npcs[0].id

    def _target_npc(self) -> Any:
        target_npc_id = self._target_npc_id()
        for npc in self.active_slice.npcs:
            if npc.id == target_npc_id:
                return npc
        raise ValueError(
            "npc response generation requires the target npc to be present in the active slice"
        )

    def to_payload(self) -> dict[str, object]:
        npc = self._target_npc()
        scene_payload: dict[str, object] | None = None
        if self.active_slice.scene is not None:
            scene_payload = {
                "id": self.active_slice.scene.id,
                "scene_type": self.active_slice.scene.scene_type,
                "location_id": self.active_slice.scene.location_id,
                "immediate_goal": self.active_slice.scene.immediate_goal,
            }
        district_payload: dict[str, object] | None = None
        if self.active_slice.district is not None:
            district_payload = {
                "id": self.active_slice.district.id,
                "name": self.active_slice.district.name,
                "lantern_condition": self.active_slice.district.lantern_condition,
                "tone": self.active_slice.district.tone,
            }
        npc = self._target_npc()
        history = [
            {"player": entry["input_text"], "npc": entry["npc_response"]}
            for entry in npc.memory_log[-6:]
            if "input_text" in entry and "npc_response" in entry
        ]
        recent_exit_lines = [
            entry["npc_exit_line"]
            for entry in npc.memory_log[-6:]
            if "npc_exit_line" in entry and isinstance(entry["npc_exit_line"], str)
        ]

        player_standing: dict[str, object] | None = None
        if self.progress is not None:
            player_standing = {
                "reputation": self.progress.reputation.tier,
                "access": self.progress.access.tier,
                "leverage": self.progress.leverage.tier,
                "can_enter_restricted_spaces": can_use_informal_access(
                    self.progress, required_access="restricted"
                ),
                "can_enter_trusted_spaces": can_use_informal_access(
                    self.progress, required_access="trusted"
                ),
                "can_pressure_npc": can_pressure_npc(
                    self.progress, evidence_strength="documented"
                ),
            }

        return {
            "task_type": "npc_response",
            "request_id": self.request_id,
            "player_input": self.player_request.input_text,
            "player_intent": self.player_request.intent,
            "conversation_history": history,
            "recent_exit_lines": recent_exit_lines,
            "player_standing": player_standing,
            "case_intro_hook": self.case_intro_text,
            "npc": {
                "id": npc.id,
                "name": npc.name,
                "role_category": npc.role_category,
                "public_identity": npc.public_identity,
                "hidden_objective_summary": npc.hidden_objective,
                "current_objective": npc.current_objective,
                "trust_in_player": npc.trust_in_player,
                "suspicion": npc.suspicion,
                "fear": npc.fear,
                "loyalty": npc.loyalty,
                "offscreen_state": npc.offscreen_state,
                "schedule_anchor": npc.schedule_anchor,
                "recent_events": npc.recent_events[-4:],
                "player_flags": npc.player_flags,
                "relationship_flags": npc.relationship_flags,
                "known_promises": npc.known_promises[-3:],
                "owed_favors": npc.owed_favors[-3:],
                "grievances": npc.grievances[-3:],
                "player_relationship": _relationship_snapshot_payload(npc, "player"),
                "loyalty_relationship": (
                    None if not npc.loyalty else _relationship_snapshot_payload(npc, npc.loyalty)
                ),
                "loyalty_faction": (
                    None
                    if self.loyalty_faction is None
                    else {
                        "id": self.loyalty_faction.id,
                        "name": self.loyalty_faction.name,
                        "style": _faction_style_label(self.loyalty_faction),
                        "tactic": _faction_tactic_label(self.loyalty_faction),
                        "attitude_toward_player": self.loyalty_faction.attitude_toward_player,
                        "active_plan": (
                            self.loyalty_faction.active_plans[0]
                            if self.loyalty_faction.active_plans
                            else "holding position"
                        ),
                    }
                ),
                "emotional_register": _emotional_register(npc),
                "institutional_pressure": _institutional_pressure_register(
                    npc,
                    loyalty_faction=self.loyalty_faction,
                ),
            },
            "scene": scene_payload,
            "district": district_payload,
            "relevant_clues": [
                {
                    "id": clue.id,
                    "clue_text": clue.clue_text,
                    "reliability": clue.reliability,
                }
                for clue in self.active_slice.clues
            ],
            "constraints": {
                "exactly_one_reply_turn": True,
                "bounded_scene_response": True,
                "cacheable_text_required": [
                    "npc_line",
                    "follow_up_suggestions",
                    "exit_line_if_needed",
                ],
            },
        }


def _emotional_register(npc: Any) -> str:
    """Translate numeric trust/fear/suspicion into plain-English behavioral guidance."""
    parts: list[str] = []
    trust = getattr(npc, "trust_in_player", 0.0)
    fear = getattr(npc, "fear", 0.0)
    suspicion = getattr(npc, "suspicion", 0.0)

    if trust < 0.2:
        parts.append("does not trust the player — deflects personal questions, gives minimum viable answers")
    elif trust < 0.45:
        parts.append("cautious toward the player — cooperative only if it costs nothing")
    else:
        parts.append("tentatively open to the player")

    if fear > 0.65:
        parts.append("afraid — hedges every statement, avoids specific details, may redirect abruptly")
    elif fear > 0.35:
        parts.append("wary — chooses words carefully, leaves exits open")

    if suspicion > 0.6:
        parts.append("actively suspicious of the player's motives — may probe back or offer partial truths to test reaction")
    elif suspicion > 0.3:
        parts.append("somewhat suspicious — watches for inconsistency in what the player says")

    return "; ".join(parts) if parts else "neutral"


def _institutional_pressure_register(
    npc: Any,
    *,
    loyalty_faction: FactionState | None,
) -> str:
    if loyalty_faction is None:
        return "no explicit institutional pressure profile is available"
    style = _faction_style_label(loyalty_faction)
    tactic = _faction_tactic_label(loyalty_faction)
    if style == "records control":
        return (
            f"under {loyalty_faction.name}'s records-control pressure — "
            f"protect names, routes, certifications, and written traces; "
            f"default tactic: {tactic}"
        )
    if style == "civic enforcement":
        return (
            f"under {loyalty_faction.name}'s civic pressure — "
            f"speak in procedural, official, or compliance-heavy language; "
            f"default tactic: {tactic}"
        )
    return f"under {loyalty_faction.name}'s institutional pressure; default tactic: {tactic}"


def _faction_style_label(faction: FactionState) -> str:
    text = " ".join(
        [
            faction.name,
            faction.public_goal,
            faction.hidden_goal,
            *faction.known_assets,
            *faction.active_plans,
        ]
    ).lower()
    if any(token in text for token in ("records", "memory", "archive", "certification", "continuity")):
        return "records control"
    if any(token in text for token in ("order", "compliance", "permit", "civic", "lantern", "public confidence")):
        return "civic enforcement"
    return "general pressure"


def _faction_tactic_label(faction: FactionState) -> str:
    plan = faction.active_plans[0].lower() if faction.active_plans else ""
    if any(token in plan for token in ("cover", "record", "certification", "delay", "correction")):
        return "burying or correcting records"
    if any(token in plan for token in ("review", "reassurance", "order", "permit", "scrutiny")):
        return "tightening official scrutiny"
    if any(token in plan for token in ("isolation", "witness")):
        return "isolating witnesses"
    if any(token in plan for token in ("fallout", "manage")):
        return "managing fallout"
    return "holding pressure"


def _relationship_snapshot_payload(npc: Any, actor_id: str) -> dict[str, object] | None:
    relationships = getattr(npc, "relationships", {})
    snapshot = relationships.get(actor_id)
    if snapshot is None:
        return None
    return {
        "actor_id": actor_id,
        "trust": snapshot.trust,
        "suspicion": snapshot.suspicion,
        "fear": snapshot.fear,
        "status": snapshot.status,
        "last_updated_at": snapshot.last_updated_at,
        "last_changed_turn": snapshot.last_changed_turn,
    }


class NPCResponseGenerator:
    def __init__(self, llm_client: SupportsJSONGeneration) -> None:
        if not isinstance(llm_client, SupportsJSONGeneration):
            raise TypeError("llm_client must provide a generate_json method")
        self._llm_client = llm_client

    def generate(
        self,
        request: NPCResponseGenerationRequest,
        max_tokens: int = 900,
    ) -> NPCResponseGenerationResult:
        try:
            payload = self._llm_client.generate_json(
                messages=self._build_messages(request),
                temperature=0.2,
                max_tokens=max_tokens,
                schema=NPCResponseGenerationResult.model_json_schema(),
            )
        except Exception as exc:
            raise NPCResponseGenerationError(str(exc)) from exc
        payload = self._sanitize_payload(payload)
        result = NPCResponseGenerationResult.model_validate(payload)
        self._validate_request_id(result, request)
        self._validate_slice_bounded_targets(result, request)
        return result

    def _sanitize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Strip structured effects entries that would fail field-level validation.

        Small models sometimes put clue or NPC ids into location-prefixed fields.
        Dropping bad entries preserves the dialogue line rather than failing entirely.
        """
        payload = sanitize_npc_response_payload(payload)
        updates = payload.get("structured_updates")
        if not isinstance(updates, dict):
            return payload
        if "redirect_targets" in updates:
            updates["redirect_targets"] = [
                t for t in updates["redirect_targets"]
                if isinstance(t, dict)
                and str(t.get("target_id", "")).startswith("location_")
                and str(t.get("target_id", "")) != _UNKNOWN_LOCATION_ID
            ]
        if "access_effects" in updates:
            updates["access_effects"] = [
                e for e in updates["access_effects"]
                if isinstance(e, dict) and (
                    e.get("target_id") is None
                    or str(e.get("target_id", "")).startswith("location_")
                )
            ]
        if "clue_effects" in updates:
            updates["clue_effects"] = [
                e for e in updates["clue_effects"]
                if isinstance(e, dict) and (
                    e.get("clue_id") is None
                    or str(e.get("clue_id", "")).startswith("clue_")
                )
            ]
        return payload

    def _validate_request_id(
        self,
        result: NPCResponseGenerationResult,
        request: NPCResponseGenerationRequest,
    ) -> None:
        if result.request_id != request.request_id:
            raise NPCResponseGenerationError(
                "npc response generation returned a mismatched request_id: "
                f"expected {request.request_id}, got {result.request_id}"
            )

    def _validate_slice_bounded_targets(
        self,
        result: NPCResponseGenerationResult,
        request: NPCResponseGenerationRequest,
    ) -> None:
        active_clue_ids = {clue.id for clue in request.active_slice.clues}
        visible_location_ids: set[str] = set()
        district = request.active_slice.district
        if district is not None:
            visible_location_ids.update(district.visible_locations)
        if request.active_slice.location is not None:
            visible_location_ids.add(request.active_slice.location.id)
        if (
            request.active_slice.scene is not None
            and request.active_slice.scene.location_id is not None
        ):
            visible_location_ids.add(request.active_slice.scene.location_id)

        for clue_effect in result.structured_updates.clue_effects:
            if clue_effect.clue_id is None:
                continue
            if clue_effect.clue_id not in active_clue_ids:
                raise NPCResponseGenerationError(
                    "structured_updates.clue_effects contains clue_id outside the active slice: "
                    f"{clue_effect.clue_id}"
                )

        for access_effect in result.structured_updates.access_effects:
            if access_effect.target_id is None:
                continue
            if access_effect.target_id not in visible_location_ids:
                raise NPCResponseGenerationError(
                    "structured_updates.access_effects contains "
                    "target_id outside the active slice: "
                    f"{access_effect.target_id}"
                )

        for redirect_target in result.structured_updates.redirect_targets:
            if redirect_target.target_id not in visible_location_ids:
                raise NPCResponseGenerationError(
                    "structured_updates.redirect_targets contains "
                    "target_id outside the active slice: "
                    f"{redirect_target.target_id}"
                )

    def _build_messages(self, request: NPCResponseGenerationRequest) -> list[dict[str, str]]:
        system_prompt = (
            "You are generating one narrow Lantern City task. "
            "The engine owns all persistent state. "
            "Return valid JSON only. "
            "Produce one bounded NPC response only. "
            "Use only the provided NPC, scene, and clue context. "
            f"{TONE_SYSTEM_BLOCK}"
        )
        schema = NPCResponseGenerationResult.model_json_schema()
        user_prompt = (
            "You are generating one bounded NPC response in Lantern City.\n"
            "Return valid JSON only.\n\n"
            "Task:\n"
            "Respond as the provided NPC to the player's immediate action.\n\n"
            "Rules:\n"
            "- stay within the NPC's known goals, fears, and knowledge\n"
            "- use npc.emotional_register to shape HOW the NPC speaks, not just what they reveal — it governs tone, deflection, and phrasing\n"
            "- if npc.loyalty_faction or npc.institutional_pressure is present, let it shape the voice of the reply:\n"
            "  records control pressure should sound careful, archival, and omission-heavy;\n"
            "  civic enforcement pressure should sound official, procedural, and compliance-minded\n"
            "- respect npc.offscreen_state, recent_events, and player_flags — they describe what changed since the last meeting and how the NPC currently approaches the player\n"
            "- generate exactly one reply turn plus structured effects\n"
            "- if the NPC refuses, the refusal should still be informative or redirective\n"
            "- preserve the game's conversation model: useful quickly, easy to leave\n"
            "- if recent_exit_lines are present and you produce a closing or exit line, do not reuse the same wording; "
            "vary the closure language while preserving the same social meaning\n"
            "- if relevant_clues are present, work the substance of applicable clues naturally into the NPC's words — "
            "the player should learn the information through what the NPC says, not from a separate label; "
            "do not quote clue_text verbatim; let the NPC express it in their own voice and register\n"
            "- if case_intro_hook is present, the NPC is introducing this case organically through conversation — "
            "weave the substance of the hook naturally into the NPC's dialogue in their own voice; "
            "do not announce it as a system event or use phrases like 'a new case' or 'lead'; "
            "the player should feel like the NPC is confiding in them, not handing them an assignment\n"
            "- if player_standing is present, use it to gate what the NPC can grant:\n"
            "  access tier Public/Restricted: NPC cannot grant entry to trusted or secret spaces;\n"
            "  reputation Wary/Known: NPC stays guarded, does not volunteer sensitive details;\n"
            "  reputation Respected+: NPC may offer more direct cooperation;\n"
            "  can_pressure_npc=false: deflect any pressure attempt without rewarding it;\n"
            "  can_pressure_npc=true: the NPC may yield or bargain if leverage is applied;\n"
            f"{NPC_DIALOGUE_RULES}\n"
            f"{COMMON_AVOID_RULES}\n\n"
            f"Request:\n{json.dumps(request.to_payload(), indent=2, sort_keys=True)}\n\n"
            f"JSON Schema:\n{json.dumps(schema, indent=2, sort_keys=True)}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]


__all__ = [
    "AccessEffect",
    "ClueEffect",
    "NPCResponseCacheableText",
    "NPCResponseGenerationError",
    "NPCResponseGenerationRequest",
    "NPCResponseGenerationResult",
    "NPCResponseGenerator",
    "NPCResponseStructuredUpdates",
    "RedirectTarget",
    "RelationshipShift",
    "SupportsJSONGeneration",
    "sanitize_npc_response_payload",
]
