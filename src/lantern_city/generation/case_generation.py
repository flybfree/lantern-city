from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import Field, field_validator

from lantern_city.generation.writing_guardrails import (
    COMMON_AVOID_RULES,
    TONE_SYSTEM_BLOCK,
)
from lantern_city.models import (
    CityState,
    DistrictState,
    FactionState,
    LanternCityModel,
    PlayerProgressState,
)


class CaseGenerationError(RuntimeError):
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


# Normalisation maps for LLM enum outputs that deviate from expected values.
# Keys are lowercase variants the LLM commonly produces; values are canonical strings.

_INTENSITY_MAP: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "moderate": "medium",
    "mid": "medium",
    "middle": "medium",
    "high": "high",
    "severe": "high",
    "intense": "high",
    "critical": "high",
}

_ROLE_CATEGORY_MAP: dict[str, str] = {
    "informant": "informant",
    "gatekeeper": "gatekeeper",
    "authority": "authority",
    "suspect": "suspect",
    "witness": "witness",
    # common LLM free-text variations → nearest canonical role
    "clerk": "gatekeeper",
    "official": "authority",
    "officer": "authority",
    "guard": "authority",
    "administrator": "authority",
    "manager": "authority",
    "supervisor": "authority",
    "foreman": "authority",
    "shift_foreman": "authority",
    "inspector": "authority",
    "warden": "authority",
    "captain": "authority",
    "commander": "authority",
    "contact": "informant",
    "source": "informant",
    "operative": "informant",
    "agent": "informant",
    "spy": "informant",
    "broker": "informant",
    "handler": "informant",
    "doorkeeper": "gatekeeper",
    "archivist": "gatekeeper",
    "registrar": "gatekeeper",
    "keeper": "gatekeeper",
    "accused": "suspect",
    "perpetrator": "suspect",
    "criminal": "suspect",
    "target": "suspect",
    "gang_leader": "suspect",
    "smuggler": "suspect",
    "bystander": "witness",
    "observer": "witness",
    "passerby": "witness",
    "worker": "witness",
    "laborer": "witness",
    "labourer": "witness",
    "wireworker": "witness",
    "dockworker": "witness",
    "factory_worker": "witness",
    "engineer": "witness",
    "technician": "witness",
    "mechanic": "witness",
    "resident": "witness",
    "citizen": "witness",
    "employee": "witness",
}

_SOURCE_TYPE_MAP: dict[str, str] = {
    "physical": "physical",
    "physical_evidence": "physical",
    "physical evidence": "physical",
    "object": "physical",
    "artifact": "physical",
    "item": "physical",
    "evidence": "physical",
    "trace": "physical",
    "material": "physical",
    "document": "document",
    "document_record": "document",
    "written": "document",
    "record": "document",
    "paper": "document",
    "file": "document",
    "ledger": "document",
    "note": "document",
    "log": "document",
    "memo": "document",
    "report": "document",
    "testimony": "testimony",
    "witness_account": "testimony",
    "witness account": "testimony",
    "witness_statement": "testimony",
    "witness statement": "testimony",
    "overheard_conversation": "testimony",
    "overheard conversation": "testimony",
    "overheard": "testimony",
    "account": "testimony",
    "statement": "testimony",
    "interview": "testimony",
    "confession": "testimony",
    "hearsay": "testimony",
    "rumor": "testimony",
    "rumour": "testimony",
    "conversation": "testimony",
    "composite": "composite",
    "combined": "composite",
    "mixed": "composite",
    "multi": "composite",
}

_RELIABILITY_MAP: dict[str, str] = {
    "credible": "credible",
    "solid": "credible",
    "reliable": "credible",
    "confirmed": "credible",
    "verified": "credible",
    "high": "credible",
    "certain": "credible",
    "uncertain": "uncertain",
    "unverified": "uncertain",
    "dubious": "uncertain",
    "questionable": "uncertain",
    "medium": "uncertain",
    "moderate": "uncertain",
    "possible": "uncertain",
    "unstable": "unstable",
    "low": "unstable",
    "shaky": "unstable",
    "unreliable": "unstable",
    "weak": "unstable",
    "suspected": "unstable",
}

_OUTCOME_STATUS_MAP: dict[str, str] = {
    "solved": "solved",
    "resolved": "solved",
    "complete": "solved",
    "completed": "solved",
    "closed": "solved",
    "success": "solved",
    "successful": "solved",
    "partially solved": "partially solved",
    "partial": "partially solved",
    "partially_solved": "partially solved",
    "partially_resolved": "partially solved",
    "partial resolution": "partially solved",
    "incomplete": "partially solved",
    "inconclusive": "partially solved",
    "failed": "failed",
    "failure": "failed",
    "escalated": "failed",
    "unsolved": "failed",
    "abandoned": "failed",
    "unresolved": "failed",
    "cold": "failed",
    "dead end": "failed",
}


def _normalize(
    value: str,
    mapping: dict[str, str],
    field_name: str,
    allowed: set[str],
    default: str | None = None,
) -> str:
    """Return the canonical value for *value* using *mapping*.

    Resolution order:
    1. Exact key lookup (underscores and spaces treated as equivalent).
    2. Prefix match: value starts with a known key or vice-versa.
    3. Substring match: any known key appears inside the value.
    4. *default* if provided.
    5. Raise ValueError.
    """
    v_under = value.strip().lower().replace("-", "_").replace(" ", "_")
    v_space = value.strip().lower()

    if v_under in mapping:
        return mapping[v_under]
    if v_space in mapping:
        return mapping[v_space]

    # Prefix match
    for key, canonical in mapping.items():
        if v_under.startswith(key) or key.startswith(v_under):
            return canonical

    # Substring match — key appears anywhere inside the value
    for key, canonical in mapping.items():
        if key in v_under:
            return canonical

    if default is not None:
        return default

    raise ValueError(f"{field_name} must be one of {allowed}, got {value!r}")


class GeneratedNPCSpec(LanternCityModel):
    name: str
    role_category: str
    district_id: str
    location_type_hint: str
    public_identity: str
    hidden_objective: str
    current_objective: str
    trust_in_player: float = Field(ge=0.0, le=1.0)
    suspicion: float = Field(ge=0.0, le=1.0)
    fear: float = Field(ge=0.0, le=1.0)

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _bounded(v, field_name="name", max_length=60)

    @field_validator("role_category")
    @classmethod
    def _v_role(cls, v: str) -> str:
        allowed = {"informant", "gatekeeper", "authority", "suspect", "witness"}
        return _normalize(v, _ROLE_CATEGORY_MAP, "role_category", allowed, default="witness")

    @field_validator("location_type_hint")
    @classmethod
    def _v_location_hint(cls, v: str) -> str:
        return _bounded(v, field_name="location_type_hint", max_length=60)

    @field_validator("public_identity")
    @classmethod
    def _v_public_identity(cls, v: str) -> str:
        return _bounded(v, field_name="public_identity", max_length=100)

    @field_validator("hidden_objective")
    @classmethod
    def _v_hidden_objective(cls, v: str) -> str:
        return _bounded(v, field_name="hidden_objective", max_length=240)

    @field_validator("current_objective")
    @classmethod
    def _v_current_objective(cls, v: str) -> str:
        return _bounded(v, field_name="current_objective", max_length=240)


class GeneratedClueSpec(LanternCityModel):
    source_type: str
    district_id: str
    location_type_hint: str
    clue_text: str
    starting_reliability: str
    known_by_npc_index: int | None = None

    @field_validator("source_type")
    @classmethod
    def _v_source_type(cls, v: str) -> str:
        allowed = {"physical", "document", "testimony", "composite"}
        return _normalize(v, _SOURCE_TYPE_MAP, "source_type", allowed, default="physical")

    @field_validator("clue_text")
    @classmethod
    def _v_clue_text(cls, v: str) -> str:
        return _bounded(v, field_name="clue_text", max_length=400)

    @field_validator("starting_reliability")
    @classmethod
    def _v_reliability(cls, v: str) -> str:
        allowed = {"credible", "uncertain", "unstable"}
        return _normalize(v, _RELIABILITY_MAP, "starting_reliability", allowed)

    @field_validator("location_type_hint")
    @classmethod
    def _v_location_hint(cls, v: str) -> str:
        return _bounded(v, field_name="location_type_hint", max_length=60)


class GeneratedResolutionPath(LanternCityModel):
    path_id: str
    label: str
    outcome_status: str
    required_clue_indices: list[int] = Field(default_factory=list, max_length=6)
    required_credible_count: int = Field(ge=0, le=8)
    summary_text: str
    fallout_text: str
    priority: int = Field(ge=1, le=5)

    @field_validator("path_id")
    @classmethod
    def _v_path_id(cls, v: str) -> str:
        return _bounded(v, field_name="path_id", max_length=60)

    @field_validator("label")
    @classmethod
    def _v_label(cls, v: str) -> str:
        return _bounded(v, field_name="label", max_length=80)

    @field_validator("outcome_status")
    @classmethod
    def _v_outcome_status(cls, v: str) -> str:
        allowed = {"solved", "partially solved", "failed"}
        return _normalize(v, _OUTCOME_STATUS_MAP, "outcome_status", allowed)

    @field_validator("summary_text")
    @classmethod
    def _v_summary(cls, v: str) -> str:
        return _bounded(v, field_name="summary_text", max_length=400)

    @field_validator("fallout_text")
    @classmethod
    def _v_fallout(cls, v: str) -> str:
        return _bounded(v, field_name="fallout_text", max_length=300)


class CaseGenerationResult(LanternCityModel):
    task_type: Literal["case_generation"] = "case_generation"
    request_id: str
    title: str
    case_type: str
    intensity: str
    opening_hook: str
    objective_summary: str
    involved_district_ids: list[str] = Field(min_length=1, max_length=5)
    npc_specs: list[GeneratedNPCSpec] = Field(min_length=1, max_length=5)
    clue_specs: list[GeneratedClueSpec] = Field(min_length=3, max_length=8)
    resolution_paths: list[GeneratedResolutionPath] = Field(min_length=2, max_length=5)

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return _bounded(v, field_name="title", max_length=80)

    @field_validator("case_type")
    @classmethod
    def _v_case_type(cls, v: str) -> str:
        return _bounded(v, field_name="case_type", max_length=60)

    @field_validator("intensity")
    @classmethod
    def _v_intensity(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        return _normalize(v, _INTENSITY_MAP, "intensity", allowed)

    @field_validator("opening_hook")
    @classmethod
    def _v_hook(cls, v: str) -> str:
        return _bounded(v, field_name="opening_hook", max_length=300)

    @field_validator("objective_summary")
    @classmethod
    def _v_objective(cls, v: str) -> str:
        return _bounded(v, field_name="objective_summary", max_length=200)


@dataclass(frozen=True, slots=True)
class CaseGenerationRequest:
    request_id: str
    city: CityState
    factions: list[FactionState]
    districts: list[DistrictState]
    progress: PlayerProgressState
    existing_case_types: list[str]
    existing_npc_names: list[str]


class CaseGenerator:
    def __init__(self, llm_client: SupportsJSONGeneration) -> None:
        if not isinstance(llm_client, SupportsJSONGeneration):
            raise TypeError("llm_client must provide a generate_json method")
        self._llm_client = llm_client

    def generate(
        self,
        request: CaseGenerationRequest,
        max_tokens: int = 3200,
    ) -> CaseGenerationResult:
        try:
            payload = self._llm_client.generate_json(
                messages=self._build_messages(request),
                temperature=0.7,
                max_tokens=max_tokens,
                schema=CaseGenerationResult.model_json_schema(),
            )
        except Exception as exc:
            raise CaseGenerationError(str(exc)) from exc
        result = CaseGenerationResult.model_validate(payload)
        if result.request_id != request.request_id:
            raise CaseGenerationError(
                f"case generation returned mismatched request_id: "
                f"expected {request.request_id}, got {result.request_id}"
            )
        return result

    def _build_messages(self, request: CaseGenerationRequest) -> list[dict[str, str]]:
        system_prompt = (
            "You are generating a new investigation case for Lantern City. "
            "The engine owns all persistent state. "
            "Return valid JSON only. "
            f"{TONE_SYSTEM_BLOCK}"
        )

        district_context = [
            {
                "id": d.id,
                "name": d.name,
                "tone": d.tone,
                "lantern_condition": d.lantern_condition,
                "access_level": d.current_access_level,
                "stability": d.stability,
            }
            for d in request.districts
        ]

        faction_context = [
            {
                "id": f.id,
                "name": f.name,
                "public_goal": f.public_goal,
                "attitude_toward_player": f.attitude_toward_player,
                "district_influence": f.influence_by_district,
                "tensions": f.tension_with_other_factions,
            }
            for f in request.factions
        ]

        progress_context = {
            "lantern_understanding": request.progress.lantern_understanding.tier,
            "access": request.progress.access.tier,
            "reputation": request.progress.reputation.tier,
            "leverage": request.progress.leverage.tier,
            "city_impact": request.progress.city_impact.tier,
        }

        user_prompt = (
            "Generate a new investigation case for Lantern City.\n"
            "Return valid JSON only.\n\n"
            f"City tension: {request.city.global_tension}\n"
            f"Missingness pressure: {request.city.missingness_pressure}\n\n"
            f"Available districts:\n{json.dumps(district_context, indent=2)}\n\n"
            f"Active factions:\n{json.dumps(faction_context, indent=2)}\n\n"
            f"Player standing: {json.dumps(progress_context)}\n\n"
            f"Existing case types to avoid duplicating: {request.existing_case_types}\n"
            f"Existing NPC names already in world (do not reuse): {request.existing_npc_names}\n\n"
            "Generation rules:\n"
            "- case must involve 2-3 districts from the available list\n"
            "- each NPC spec must specify a district_id from the available districts\n"
            "- each clue spec must specify a district_id from the available districts\n"
            "- location_type_hint: describe the kind of physical space "
            "(e.g. 'archive', 'service passage', 'storage', 'outdoor', 'administrative office')\n"
            "- known_by_npc_index: 0-based index into npc_specs for the NPC who knows this clue, "
            "or null if the clue is discovered through location inspection\n"
            "- resolution_paths: priority 1 = best outcome checked first, "
            "higher numbers = worse fallback paths\n"
            "- required_clue_indices: indices into clue_specs that must be credible for this path\n"
            "- opening_hook: 1-2 sentences surfaced as a rumor or observation when the player "
            "enters one of the involved districts — civic, grounded, no magic\n"
            f"- {COMMON_AVOID_RULES}\n\n"
            f"request_id: {request.request_id}\n\n"
            f"JSON Schema:\n{json.dumps(CaseGenerationResult.model_json_schema(), indent=2)}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]


__all__ = [
    "CaseGenerationError",
    "CaseGenerationRequest",
    "CaseGenerationResult",
    "CaseGenerator",
    "GeneratedClueSpec",
    "GeneratedNPCSpec",
    "GeneratedResolutionPath",
    "SupportsJSONGeneration",
]
