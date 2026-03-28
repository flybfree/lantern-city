from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from lantern_city.seed_schema import CitySeedDocument, validate_city_seed


class CitySeedGenerationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CitySeedGenerationRequest:
    request_id: str
    schema_version: str = "1.0"
    city_scale: str = "mvp"
    seed_parameters: dict[str, Any] = field(default_factory=dict)


class CitySeedGenerator:
    def __init__(self, llm_client: Any) -> None:
        self._llm_client = llm_client

    def generate(self, request: CitySeedGenerationRequest) -> CitySeedDocument:
        messages = self._build_messages(request)
        try:
            payload = self._llm_client.generate_json(
                messages=messages,
                temperature=0.2,
                max_tokens=2400,
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
            "Keep the city recognizably Lantern City: noir, wet, civic, memory-strained, lantern-centered."
        )
        request_payload = {
            "task_type": "city_seed",
            "request_id": request.request_id,
            "schema_version": request.schema_version,
            "city_scale": request.city_scale,
            "seed_parameters": request.seed_parameters,
            "constraints": {
                "must_return_json": True,
                "match_schema": "city_seed_v1",
                "narrow_scope": True,
            },
        }
        user_prompt = (
            "Generate a new Lantern City seed matching the documented schema.\n"
            "Return the seed object only.\n"
            f"Request:\n{json.dumps(request_payload, indent=2, sort_keys=True)}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]


__all__ = ["CitySeedGenerationError", "CitySeedGenerationRequest", "CitySeedGenerator"]
