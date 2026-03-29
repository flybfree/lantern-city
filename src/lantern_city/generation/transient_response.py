"""LLM generation for transient NPC encounter narrative.

Transients are ephemeral — no clues, no persistent state.
The LLM provides atmospheric depth: a richer encounter description
and an optional brief spoken line. Effects are always determined
procedurally by the caller, never by this module.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import Field, field_validator

from lantern_city.generation.writing_guardrails import (
    COMMON_AVOID_RULES,
    NPC_DIALOGUE_RULES,
    TONE_SYSTEM_BLOCK,
)
from lantern_city.models import LanternCityModel


class TransientGenerationError(RuntimeError):
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


def _bounded(value: str, *, field_name: str, max_length: int) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must be non-empty")
    if len(value) > max_length:
        raise ValueError(f"{field_name} must be under {max_length} chars")
    return value


class TransientEncounterResult(LanternCityModel):
    """LLM-generated content for a transient NPC encounter."""
    narrative: str = Field(description="2-3 sentences describing the transient and what happens.")
    spoken_line: str | None = Field(
        default=None,
        description="A single line the transient says, or null if they say nothing.",
    )

    @field_validator("narrative")
    @classmethod
    def _v_narrative(cls, v: str) -> str:
        return _bounded(v, field_name="narrative", max_length=400)

    @field_validator("spoken_line")
    @classmethod
    def _v_spoken_line(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 160:
            raise ValueError("spoken_line must be under 160 chars")
        return v


def generate_transient_encounter(
    *,
    archetype: str,
    district_name: str,
    lantern_condition: str,
    global_tension: float,
    llm_client: SupportsJSONGeneration,
    max_tokens: int = 400,
) -> TransientEncounterResult:
    """Call the LLM to generate atmospheric encounter narrative for a transient NPC."""
    system_prompt = (
        "You are writing a brief transient NPC encounter for Lantern City, a text-based "
        "investigative game set in a noir city where lanterns affect memory and truth. "
        "The encounter is atmospheric only — no clues, no case information. "
        "Write a 2-3 sentence description of what this person looks like and does, "
        "plus an optional single line they say (or null if they say nothing). "
        f"{TONE_SYSTEM_BLOCK}"
    )
    tension_label = "low" if global_tension < 0.33 else ("medium" if global_tension < 0.67 else "high")
    user_prompt = (
        f"District: {district_name}\n"
        f"Lantern condition: {lantern_condition}\n"
        f"City tension: {tension_label}\n"
        f"Transient archetype: {archetype}\n\n"
        "Write a brief encounter. This person is not involved in any case. "
        "They might say something atmospheric, something that reveals district texture, "
        "or nothing at all. They do not offer clues or advance any investigation.\n"
        f"- {NPC_DIALOGUE_RULES}\n"
        f"- {COMMON_AVOID_RULES}\n\n"
        f"JSON schema:\n"
        "{ \"narrative\": \"string (2-3 sentences)\", \"spoken_line\": \"string or null\" }"
    )
    try:
        payload = llm_client.generate_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.85,
            max_tokens=max_tokens,
            schema=TransientEncounterResult.model_json_schema(),
        )
    except Exception as exc:
        raise TransientGenerationError(str(exc)) from exc
    return TransientEncounterResult.model_validate(payload)


__all__ = [
    "TransientEncounterResult",
    "TransientGenerationError",
    "generate_transient_encounter",
    "SupportsJSONGeneration",
]
