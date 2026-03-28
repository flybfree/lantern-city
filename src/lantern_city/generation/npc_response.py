from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from lantern_city.active_slice import ActiveSlice
from lantern_city.models import LanternCityModel, PlayerRequest


class NPCResponseGenerationError(RuntimeError):
    pass


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
    trust_delta: float = 0.0
    suspicion_delta: float = 0.0
    fear_delta: float = 0.0
    tag: str | None = None


class ClueEffect(LanternCityModel):
    effect_type: str
    clue_id: str | None = None
    note: str


class AccessEffect(LanternCityModel):
    effect_type: str
    target_id: str | None = None
    note: str


class RedirectTarget(LanternCityModel):
    target_type: str
    target_id: str
    reason: str


class NPCResponseStructuredUpdates(LanternCityModel):
    dialogue_act: str
    npc_stance: str
    relationship_shift: RelationshipShift
    clue_effects: list[ClueEffect] = Field(default_factory=list, max_length=3)
    access_effects: list[AccessEffect] = Field(default_factory=list, max_length=3)
    redirect_targets: list[RedirectTarget] = Field(default_factory=list, max_length=3)


class NPCResponseCacheableText(LanternCityModel):
    npc_line: str
    follow_up_suggestions: list[str] = Field(min_length=1, max_length=4)
    exit_line_if_needed: str | None = None


class NPCResponseGenerationResult(LanternCityModel):
    task_type: str = "npc_response"
    request_id: str
    summary_text: str
    structured_updates: NPCResponseStructuredUpdates
    cacheable_text: NPCResponseCacheableText
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


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
        npc_id = self.npc_id or self.player_request.target_id or self.active_slice.npcs[0].id
        if npc_id not in {npc.id for npc in self.active_slice.npcs}:
            raise ValueError("npc response generation requires the target npc to be present in the active slice")

    def to_payload(self) -> dict[str, object]:
        npc_id = self.npc_id or self.player_request.target_id or self.active_slice.npcs[0].id
        npc = next(npc for npc in self.active_slice.npcs if npc.id == npc_id)
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
        return NPCResponseGenerationResult.model_validate(payload)

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
