from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from lantern_city.seed_schema import CitySeedDocument, validate_city_seed


class CitySeedGenerationError(RuntimeError):
    pass


JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


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


@dataclass(frozen=True, slots=True)
class CitySeedGenerationRequest:
    request_id: str
    schema_version: str = "1.0"
    city_scale: str = "mvp"
    seed_parameters: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "request_id",
            self._require_non_empty_string("request_id", self.request_id),
        )
        object.__setattr__(
            self,
            "schema_version",
            self._require_non_empty_string("schema_version", self.schema_version),
        )
        object.__setattr__(
            self,
            "city_scale",
            self._require_non_empty_string("city_scale", self.city_scale),
        )
        object.__setattr__(
            self,
            "seed_parameters",
            self._validate_seed_parameters(self.seed_parameters),
        )

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "request_id": self.request_id,
            "schema_version": self.schema_version,
            "city_scale": self.city_scale,
            "seed_parameters": self.seed_parameters,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), indent=2, sort_keys=True)

    @staticmethod
    def _require_non_empty_string(field_name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()

    @classmethod
    def _validate_seed_parameters(
        cls, value: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        if not isinstance(value, dict):
            raise ValueError("seed_parameters must be a JSON object")
        if any(not isinstance(key, str) for key in value):
            raise ValueError("seed_parameters keys must be strings")
        try:
            json.dumps(value, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("seed_parameters must be JSON-serializable") from exc
        return value


class CitySeedGenerator:
    def __init__(self, llm_client: SupportsJSONGeneration) -> None:
        if not isinstance(llm_client, SupportsJSONGeneration):
            raise TypeError("llm_client must provide a generate_json method")
        self._llm_client = llm_client

    def generate(self, request: CitySeedGenerationRequest) -> CitySeedDocument:
        messages = self._build_messages(request)
        schema = CitySeedDocument.model_json_schema()
        try:
            payload = self._llm_client.generate_json(
                messages=messages,
                temperature=0.2,
                max_tokens=2400,
                schema=schema,
            )
        except Exception as exc:
            raise CitySeedGenerationError(str(exc)) from exc
        return validate_city_seed(payload)

    def _build_messages(self, request: CitySeedGenerationRequest) -> list[dict[str, str]]:
        system_prompt = (
            "You are generating one narrow Lantern City task. "
            "The engine owns all persistent state. "
            "Return valid JSON only. "
            "Do not add fields outside the requested schema. "
            "Keep the city recognizably Lantern City: noir, wet, civic, "
            "memory-strained, lantern-centered."
        )
        request_payload = {
            "task_type": "city_seed",
            **request.to_payload(),
            "constraints": {
                "must_return_json": True,
                "return_only_seed_object": True,
                "narrow_scope": True,
            },
        }
        schema = CitySeedDocument.model_json_schema()
        user_prompt = (
            "Generate a new Lantern City seed that matches the JSON Schema below exactly.\n"
            "Return the seed object only. Do not wrap it in markdown.\n\n"
            f"Request:\n{json.dumps(request_payload, indent=2, sort_keys=True)}\n\n"
            f"JSON Schema:\n{json.dumps(schema, indent=2, sort_keys=True)}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]


__all__ = [
    "CitySeedGenerationError",
    "CitySeedGenerationRequest",
    "CitySeedGenerator",
    "SupportsJSONGeneration",
]
