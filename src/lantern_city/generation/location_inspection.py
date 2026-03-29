from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import Field, field_validator

from lantern_city.active_slice import ActiveSlice
from lantern_city.generation.writing_guardrails import (
    COMMON_AVOID_RULES,
    SCENE_NARRATION_RULES,
    TONE_SYSTEM_BLOCK,
)
from lantern_city.models import LanternCityModel, PlayerRequest


class LocationInspectionError(RuntimeError):
    pass


def _require_bounded_text(value: str, *, field_name: str, max_length: int) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    if len(value) > max_length:
        raise ValueError(f"{field_name} must stay under {max_length} characters")
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


class LocationInspectionResult(LanternCityModel):
    task_type: Literal["location_inspect"] = "location_inspect"
    request_id: str
    scene_text: str
    notable_details: list[str] = Field(min_length=1, max_length=4)
    lantern_effect: str | None = None
    clue_connection: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("scene_text")
    @classmethod
    def _validate_scene_text(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="scene_text", max_length=600)

    @field_validator("notable_details")
    @classmethod
    def _validate_notable_details(cls, value: list[str]) -> list[str]:
        return [
            _require_bounded_text(item, field_name="notable_details", max_length=200)
            for item in value
        ]

    @field_validator("lantern_effect")
    @classmethod
    def _validate_lantern_effect(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_bounded_text(value, field_name="lantern_effect", max_length=240)

    @field_validator("clue_connection")
    @classmethod
    def _validate_clue_connection(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_bounded_text(value, field_name="clue_connection", max_length=400)


@dataclass(frozen=True, slots=True)
class LocationInspectionRequest:
    request_id: str
    active_slice: ActiveSlice
    player_request: PlayerRequest

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        if self.active_slice.location is None and self.active_slice.district is None:
            raise ValueError("location inspection requires a location or district in the active slice")

    @property
    def focus_object(self) -> str | None:
        text = self.player_request.input_text.strip()
        return text if text else None

    def to_payload(self) -> dict[str, object]:
        location_payload: dict[str, object] | None = None
        if self.active_slice.location is not None:
            loc = self.active_slice.location
            location_payload = {
                "id": loc.id,
                "name": loc.name,
                "location_type": loc.location_type,
                "known_npc_ids": loc.known_npc_ids,
                "clue_ids": loc.clue_ids,
                "scene_objects": loc.scene_objects,
            }

        district_payload: dict[str, object] | None = None
        if self.active_slice.district is not None:
            d = self.active_slice.district
            district_payload = {
                "id": d.id,
                "name": d.name,
                "lantern_condition": d.lantern_condition,
                "tone": d.tone,
            }

        clue_payload = [
            {
                "id": clue.id,
                "clue_text": clue.clue_text,
                "reliability": clue.reliability,
                "source_type": clue.source_type,
            }
            for clue in self.active_slice.clues
        ]

        npc_payload = [
            {
                "id": npc.id,
                "name": npc.name,
                "role_category": npc.role_category,
                "public_identity": npc.public_identity,
            }
            for npc in self.active_slice.npcs
        ]

        return {
            "task_type": "location_inspect",
            "request_id": self.request_id,
            "location": location_payload,
            "district": district_payload,
            "present_npcs": npc_payload,
            "relevant_clues": clue_payload,
            "focus_object": self.focus_object,
            "constraints": {
                "scene_text_required": True,
                "notable_details_count": "1 to 4",
                "lantern_effect_if_notable": True,
                "clue_connection_if_present": True,
                "no_new_facts_beyond_context": True,
            },
        }


class LocationInspectionGenerator:
    def __init__(self, llm_client: SupportsJSONGeneration) -> None:
        if not isinstance(llm_client, SupportsJSONGeneration):
            raise TypeError("llm_client must provide a generate_json method")
        self._llm_client = llm_client

    def generate(
        self,
        request: LocationInspectionRequest,
        max_tokens: int = 1200,
    ) -> LocationInspectionResult:
        try:
            payload = self._llm_client.generate_json(
                messages=self._build_messages(request),
                temperature=0.3,
                max_tokens=max_tokens,
                schema=LocationInspectionResult.model_json_schema(),
            )
        except Exception as exc:
            raise LocationInspectionError(str(exc)) from exc
        result = LocationInspectionResult.model_validate(payload)
        if result.request_id != request.request_id:
            raise LocationInspectionError(
                f"location inspection returned mismatched request_id: "
                f"expected {request.request_id}, got {result.request_id}"
            )
        return result

    def _build_messages(self, request: LocationInspectionRequest) -> list[dict[str, str]]:
        system_prompt = (
            "You are generating one narrow Lantern City task. "
            "The engine owns all persistent state. "
            "Return valid JSON only. "
            "Describe only what is physically observable at this location. "
            f"{TONE_SYSTEM_BLOCK}"
        )
        schema = LocationInspectionResult.model_json_schema()
        if request.focus_object:
            task_line = (
                f'Describe what the player observes when closely examining "{request.focus_object}" '
                f"at this location."
            )
            rules = (
                "- focus entirely on the named object — its physical state, detail, and condition\n"
                "- notable_details should be specific findings from examining this object closely\n"
                "- lantern_effect should describe how current light conditions affect examination of this object\n"
                "- if the object connects to a known clue, describe that connection physically — never mention clue IDs or internal identifiers\n"
                "- do not describe the broader room; stay on the object\n"
                "- do not invent facts not supported by the provided context\n"
                "- keep scene_text to 2-3 sentences\n"
                f"{SCENE_NARRATION_RULES}\n"
                f"{COMMON_AVOID_RULES}\n"
            )
        else:
            task_line = "Describe what the player observes when inspecting this location."
            rules = (
                "- ground the scene in the physical space and its lantern condition\n"
                "- notable_details should be specific, observable, and investigatively useful\n"
                "- if relevant clues are present, acknowledge what the physical space reveals about them\n"
                "- lantern_effect should describe how the current lantern state shapes what is visible\n"
                "- do not invent facts not supported by the provided context\n"
                "- keep scene_text to 2-4 sentences\n"
                f"{SCENE_NARRATION_RULES}\n"
                f"{COMMON_AVOID_RULES}\n"
            )
        user_prompt = (
            "You are generating a location inspection result for Lantern City.\n"
            "Return valid JSON only.\n\n"
            f"Task:\n{task_line}\n\n"
            f"Rules:\n{rules}\n"
            f"Request:\n{json.dumps(request.to_payload(), indent=2, sort_keys=True)}\n\n"
            f"JSON Schema:\n{json.dumps(schema, indent=2, sort_keys=True)}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]


__all__ = [
    "LocationInspectionError",
    "LocationInspectionGenerator",
    "LocationInspectionRequest",
    "LocationInspectionResult",
    "SupportsJSONGeneration",
]
