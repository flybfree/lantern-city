from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import Field, field_validator

from lantern_city.active_slice import ActiveSlice
from lantern_city.models import LanternCityModel, PlayerRequest


class NPCResponseGenerationError(RuntimeError):
    pass


RELATIONSHIP_DELTA_MIN = -1.0
RELATIONSHIP_DELTA_MAX = 1.0


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
        return _require_prefixed_id(value, field_name="target_id", prefix="location_", max_length=80)

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
        return _require_prefixed_id(value, field_name="target_id", prefix="location_", max_length=80)

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
        return _require_single_turn_text(value, field_name="npc_line", max_length=280)

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
        return _require_bounded_text(value, field_name="summary_text", max_length=160)

    @field_validator("warnings")
    @classmethod
    def _validate_warnings(cls, value: list[str]) -> list[str]:
        return [_require_bounded_text(item, field_name="warnings", max_length=120) for item in value]


@dataclass(frozen=True, slots=True)
class NPCResponseGenerationRequest:
    request_id: str
    active_slice: ActiveSlice
    player_request: PlayerRequest
    npc_id: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        if not self.active_slice.npcs:
            raise ValueError("npc response generation requires at least one npc in the active slice")
        self._target_npc()

    def _target_npc_id(self) -> str:
        return self.npc_id or self.player_request.target_id or self.active_slice.npcs[0].id

    def _target_npc(self) -> Any:
        target_npc_id = self._target_npc_id()
        for npc in self.active_slice.npcs:
            if npc.id == target_npc_id:
                return npc
        raise ValueError("npc response generation requires the target npc to be present in the active slice")

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
        return {
            "task_type": "npc_response",
            "request_id": self.request_id,
            "player_input": self.player_request.input_text,
            "player_intent": self.player_request.intent,
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


class NPCResponseGenerator:
    def __init__(self, llm_client: SupportsJSONGeneration) -> None:
        if not isinstance(llm_client, SupportsJSONGeneration):
            raise TypeError("llm_client must provide a generate_json method")
        self._llm_client = llm_client

    def generate(self, request: NPCResponseGenerationRequest) -> NPCResponseGenerationResult:
        try:
            payload = self._llm_client.generate_json(
                messages=self._build_messages(request),
                temperature=0.2,
                max_tokens=900,
                schema=NPCResponseGenerationResult.model_json_schema(),
            )
        except Exception as exc:
            raise NPCResponseGenerationError(str(exc)) from exc
        result = NPCResponseGenerationResult.model_validate(payload)
        self._validate_request_id(result, request)
        self._validate_slice_bounded_targets(result, request)
        return result

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
        if request.active_slice.scene is not None and request.active_slice.scene.location_id is not None:
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
                    "structured_updates.access_effects contains target_id outside the active slice: "
                    f"{access_effect.target_id}"
                )

        for redirect_target in result.structured_updates.redirect_targets:
            if redirect_target.target_id not in visible_location_ids:
                raise NPCResponseGenerationError(
                    "structured_updates.redirect_targets contains target_id outside the active slice: "
                    f"{redirect_target.target_id}"
                )

    def _build_messages(self, request: NPCResponseGenerationRequest) -> list[dict[str, str]]:
        system_prompt = (
            "You are generating one narrow Lantern City task. "
            "The engine owns all persistent state. "
            "Return valid JSON only. "
            "Produce one bounded NPC response only. "
            "Use only the provided NPC, scene, and clue context. "
            "Tone: restrained, character-specific, no exposition dump."
        )
        schema = NPCResponseGenerationResult.model_json_schema()
        user_prompt = (
            "You are generating one bounded NPC response in Lantern City.\n"
            "Return valid JSON only.\n\n"
            "Task:\n"
            "Respond as the provided NPC to the player's immediate action.\n\n"
            "Rules:\n"
            "- stay within the NPC's known goals, fears, and knowledge\n"
            "- generate exactly one reply turn plus structured effects\n"
            "- if the NPC refuses, the refusal should still be informative or redirective\n"
            "- preserve the game's conversation model: useful quickly, easy to leave\n\n"
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
]
