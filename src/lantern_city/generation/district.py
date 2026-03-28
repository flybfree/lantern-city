from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import Field, field_validator, model_validator

from lantern_city.active_slice import ActiveSlice
from lantern_city.models import LanternCityModel


class DistrictGenerationError(RuntimeError):
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


class DistrictLocation(LanternCityModel):
    location_id: str
    name: str
    location_type: str
    short_description: str
    playable_hook: str

    @field_validator("location_id", "name", "location_type", "short_description", "playable_hook")
    @classmethod
    def _require_non_empty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("district location fields must be non-empty strings")
        return value

    @field_validator("location_type")
    @classmethod
    def _bound_location_type(cls, value: str) -> str:
        if len(value) > 60:
            raise ValueError("location_type must stay compact")
        return value

    @field_validator("short_description", "playable_hook")
    @classmethod
    def _bound_local_text(cls, value: str) -> str:
        if len(value) > 180:
            raise ValueError("district location text must stay compact and local")
        return value


class NPCAnchorSpec(LanternCityModel):
    npc_id: str | None = None
    name: str
    role: str
    local_relevance: str

    @field_validator("name", "role", "local_relevance")
    @classmethod
    def _require_non_empty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("npc anchor fields must be non-empty strings")
        return value

    @field_validator("npc_id")
    @classmethod
    def _validate_npc_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not value.startswith("npc_"):
            raise ValueError("npc anchor ids must look like local npc ids")
        return value

    @field_validator("name", "role")
    @classmethod
    def _bound_short_text(cls, value: str) -> str:
        if len(value) > 80:
            raise ValueError("npc anchor names and roles must stay compact")
        return value

    @field_validator("local_relevance")
    @classmethod
    def _bound_local_relevance(cls, value: str) -> str:
        if len(value) > 160:
            raise ValueError("npc anchor relevance must stay compact and local")
        return value

    @model_validator(mode="after")
    def _require_local_anchor_reference(self) -> NPCAnchorSpec:
        if self.npc_id is None and (not self.name or not self.role or not self.local_relevance):
            raise ValueError("npc anchor specs must provide either an npc_id or a complete local spec")
        return self


class DistrictStructuredUpdates(LanternCityModel):
    district_summary: str
    major_locations: list[DistrictLocation] = Field(min_length=3, max_length=5)
    local_problems: list[str] = Field(min_length=1, max_length=4)
    rumor_lines: list[str] = Field(min_length=1, max_length=5)
    npc_anchor_ids_or_specs: list[NPCAnchorSpec] = Field(max_length=5)

    @field_validator("district_summary")
    @classmethod
    def _validate_district_summary(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="district_summary", max_length=240)

    @field_validator("local_problems")
    @classmethod
    def _validate_local_problems(cls, value: list[str]) -> list[str]:
        return [
            _require_bounded_text(item, field_name="local_problems", max_length=140)
            for item in value
        ]

    @field_validator("rumor_lines")
    @classmethod
    def _validate_rumor_lines(cls, value: list[str]) -> list[str]:
        return [
            _require_bounded_text(item, field_name="rumor_lines", max_length=140)
            for item in value
        ]


class DistrictCacheableText(LanternCityModel):
    entry_text: str
    short_summary: str

    @field_validator("entry_text")
    @classmethod
    def _validate_entry_text(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="entry_text", max_length=320)

    @field_validator("short_summary")
    @classmethod
    def _validate_short_summary(cls, value: str) -> str:
        return _require_bounded_text(value, field_name="short_summary", max_length=160)


class DistrictGenerationResult(LanternCityModel):
    task_type: Literal["district_expand"] = "district_expand"
    request_id: str
    summary_text: str
    structured_updates: DistrictStructuredUpdates
    cacheable_text: DistrictCacheableText
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DistrictGenerationRequest:
    request_id: str
    active_slice: ActiveSlice
    city_identity_summary: str
    faction_footprint: list[str] = field(default_factory=list)
    missingness_pressure: float | None = None

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        if self.active_slice.district is None:
            raise ValueError("district generation requires an active district")
        if not self.city_identity_summary.strip():
            raise ValueError("city_identity_summary must be a non-empty string")

    def to_payload(self) -> dict[str, object]:
        district = self.active_slice.district
        assert district is not None
        district_payload = {
            "id": district.id,
            "name": district.name,
            "tone": district.tone,
            "lantern_condition": district.lantern_condition,
            "governing_power": district.governing_power,
            "active_problems": district.active_problems,
            "visible_locations": district.visible_locations,
            "relevant_npc_ids": district.relevant_npc_ids,
            "rumor_pool": district.rumor_pool,
            "current_access_level": district.current_access_level,
        }
        npc_payload = [
            {
                "id": npc.id,
                "name": npc.name,
                "role_category": npc.role_category,
                "public_identity": npc.public_identity,
                "current_objective": npc.current_objective,
            }
            for npc in self.active_slice.npcs
        ]
        case_payload: dict[str, object] | None = None
        if self.active_slice.case is not None:
            case_payload = {
                "id": self.active_slice.case.id,
                "title": self.active_slice.case.title,
                "objective_summary": self.active_slice.case.objective_summary,
                "open_questions": self.active_slice.case.open_questions,
            }
        return {
            "task_type": "district_expand",
            "request_id": self.request_id,
            "city_identity_summary": self.city_identity_summary,
            "district": district_payload,
            "faction_footprint": self.faction_footprint,
            "missingness_pressure": self.missingness_pressure,
            "visible_npc_anchors": npc_payload,
            "active_case": case_payload,
            "constraints": {
                "current_district_slice_only": True,
                "min_major_locations": 3,
                "max_major_locations": 5,
                "short_rumors_only": True,
                "cacheable_text_required": ["entry_text", "short_summary"],
            },
        }


class DistrictGenerator:
    def __init__(self, llm_client: SupportsJSONGeneration) -> None:
        if not isinstance(llm_client, SupportsJSONGeneration):
            raise TypeError("llm_client must provide a generate_json method")
        self._llm_client = llm_client

    def generate(self, request: DistrictGenerationRequest) -> DistrictGenerationResult:
        try:
            payload = self._llm_client.generate_json(
                messages=self._build_messages(request),
                temperature=0.2,
                max_tokens=1200,
                schema=DistrictGenerationResult.model_json_schema(),
            )
        except Exception as exc:
            raise DistrictGenerationError(str(exc)) from exc
        return DistrictGenerationResult.model_validate(payload)

    def _build_messages(self, request: DistrictGenerationRequest) -> list[dict[str, str]]:
        system_prompt = (
            "You are generating one narrow Lantern City task. "
            "The engine owns all persistent state. "
            "Return valid JSON only. "
            "Keep the result to the current district slice only. "
            "Use only the provided district context and known IDs. "
            "Tone: restrained, atmospheric, civic, legible."
        )
        schema = DistrictGenerationResult.model_json_schema()
        user_prompt = (
            "You are expanding one Lantern City district for active play.\n"
            "Return valid JSON only.\n\n"
            "Task:\n"
            "Create only the district slice needed for current play.\n\n"
            "Rules:\n"
            "- use the provided district identity and state as truth\n"
            "- produce the district slice needed for current play\n"
            "- give 3 to 5 useful major locations at most for the MVP slice\n"
            "- include rumor lines that imply, not solve\n"
            "- keep output compact and cacheable\n\n"
            f"Request:\n{json.dumps(request.to_payload(), indent=2, sort_keys=True)}\n\n"
            f"JSON Schema:\n{json.dumps(schema, indent=2, sort_keys=True)}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]


__all__ = [
    "DistrictCacheableText",
    "DistrictGenerationError",
    "DistrictGenerationRequest",
    "DistrictGenerationResult",
    "DistrictGenerator",
    "DistrictLocation",
    "DistrictStructuredUpdates",
    "NPCAnchorSpec",
    "SupportsJSONGeneration",
]
