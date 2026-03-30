"""City seed generation for Lantern City.

Two-phase LLM generation:
  Phase 1 — city framework: identity, districts, factions, lantern, missingness, tone
  Phase 2 — cases + NPCs + progression (district/faction IDs from phase 1 provided as context)

The assembled payload is validated against CitySeedDocument before returning.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from lantern_city.seed_schema import CitySeedDocument, validate_city_seed


class CitySeedGenerationError(RuntimeError):
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


# ── Phase 1: city framework ───────────────────────────────────────────────────

_DISTRICT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "snake_case, must start with district_"},
        "name": {"type": "string"},
        "role": {"type": "string"},
        "stability_baseline": {"type": "number"},
        "lantern_state": {"type": "string", "enum": ["bright", "dim", "flickering", "extinguished", "altered"]},
        "access_pattern": {"type": "string"},
        "hidden_location_density": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["id", "name", "role", "stability_baseline", "lantern_state", "access_pattern", "hidden_location_density"],
    "additionalProperties": False,
}

_FACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "snake_case, must start with faction_"},
        "name": {"type": "string"},
        "role": {"type": "string"},
        "public_goal": {"type": "string"},
        "hidden_goal": {"type": "string"},
        "influence_by_district": {
            "type": "object",
            "additionalProperties": {"type": "number"},
            "description": "district_id → influence float 0.0–1.0",
        },
        "attitude_toward_player": {"type": "string"},
    },
    "required": ["id", "name", "role", "public_goal", "hidden_goal", "influence_by_district", "attitude_toward_player"],
    "additionalProperties": False,
}

_FRAMEWORK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "city_name": {"type": "string"},
        "dominant_mood": {"type": "array", "items": {"type": "string"}},
        "weather_pattern": {"type": "array", "items": {"type": "string"}},
        "architectural_style": {"type": "array", "items": {"type": "string"}},
        "economic_character": {"type": "array", "items": {"type": "string"}},
        "social_texture": {"type": "array", "items": {"type": "string"}},
        "ritual_texture": {"type": "array", "items": {"type": "string"}},
        "baseline_noise_level": {"type": "string", "enum": ["low", "medium", "high"]},
        "districts": {"type": "array", "items": _DISTRICT_SCHEMA},
        "factions": {"type": "array", "items": _FACTION_SCHEMA},
        "tension_map": {
            "type": "object",
            "additionalProperties": {"type": "number"},
            "description": "Keys must use format 'faction_a_id|faction_b_id'",
        },
        "lantern_system_style": {"type": "string"},
        "lantern_ownership_structure": {"type": "string"},
        "lantern_maintenance_structure": {"type": "string"},
        "lantern_condition_distribution": {
            "type": "object",
            "properties": {
                "bright": {"type": "number"},
                "dim": {"type": "number"},
                "flickering": {"type": "number"},
                "extinguished": {"type": "number"},
                "altered": {"type": "number"},
            },
            "required": ["bright", "dim", "flickering", "extinguished", "altered"],
            "additionalProperties": False,
        },
        "lantern_reach_profile": {"type": "string"},
        "lantern_social_effect_profile": {"type": "array", "items": {"type": "string"}},
        "lantern_memory_effect_profile": {"type": "array", "items": {"type": "string"}},
        "lantern_tampering_probability": {"type": "number"},
        "missingness_pressure": {"type": "number"},
        "missingness_scope": {"type": "string"},
        "missingness_visibility": {"type": "string"},
        "missingness_style": {"type": "string"},
        "missingness_targets": {"type": "array", "items": {"type": "string"}},
        "missingness_risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
        "story_density": {"type": "string"},
        "mystery_complexity": {"type": "string"},
        "social_resistance": {"type": "string"},
        "investigation_pace": {"type": "string"},
        "consequence_severity": {"type": "string"},
        "revelation_delay": {"type": "string"},
        "narrative_strangeness": {"type": "string"},
    },
    "required": [
        "city_name", "dominant_mood", "weather_pattern", "architectural_style",
        "economic_character", "social_texture", "ritual_texture", "baseline_noise_level",
        "districts", "factions", "tension_map",
        "lantern_system_style", "lantern_ownership_structure", "lantern_maintenance_structure",
        "lantern_condition_distribution", "lantern_reach_profile",
        "lantern_social_effect_profile", "lantern_memory_effect_profile",
        "lantern_tampering_probability",
        "missingness_pressure", "missingness_scope", "missingness_visibility",
        "missingness_style", "missingness_targets", "missingness_risk_level",
        "story_density", "mystery_complexity", "social_resistance", "investigation_pace",
        "consequence_severity", "revelation_delay", "narrative_strangeness",
    ],
    "additionalProperties": False,
}

# ── Phase 2: cases + NPCs + progression ──────────────────────────────────────

_CASE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "snake_case, must start with case_"},
        "type": {"type": "string"},
        "intensity": {"type": "string", "enum": ["low", "medium", "high"]},
        "scope": {"type": "string"},
        "involved_district_ids": {"type": "array", "items": {"type": "string"}},
        "involved_faction_ids": {"type": "array", "items": {"type": "string"}},
        "key_npc_ids": {"type": "array", "items": {"type": "string"}},
        "failure_modes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["id", "type", "intensity", "scope", "involved_district_ids",
                 "involved_faction_ids", "key_npc_ids", "failure_modes"],
    "additionalProperties": False,
}

_NPC_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "snake_case, must start with npc_"},
        "name": {"type": "string"},
        "role_category": {
            "type": "string",
            "enum": ["informant", "gatekeeper", "authority", "suspect", "witness"],
        },
        "district_id": {"type": "string", "description": "Must be one of the valid district IDs"},
        "location_id": {
            "type": "string",
            "description": "Use 'location_tbd' — will be assigned during world generation",
        },
        "memory_depth": {"type": "string", "enum": ["low", "medium", "high"]},
        "relationship_density": {"type": "string", "enum": ["low", "medium", "high"]},
        "secrecy_level": {"type": "string", "enum": ["low", "medium", "high", "extreme"]},
        "mobility_pattern": {"type": "string"},
        "relevance_level": {
            "type": "string",
            "enum": ["background", "low", "secondary", "medium", "high", "immediate", "critical"],
        },
    },
    "required": [
        "id", "name", "role_category", "district_id", "location_id",
        "memory_depth", "relationship_density", "secrecy_level",
        "mobility_pattern", "relevance_level",
    ],
    "additionalProperties": False,
}

_CASES_NPCS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cases": {"type": "array", "items": _CASE_SCHEMA},
        "npcs": {"type": "array", "items": _NPC_SCHEMA},
        "starting_lantern_understanding": {"type": "integer"},
        "starting_access": {"type": "integer"},
        "starting_reputation": {"type": "integer"},
        "starting_leverage": {"type": "integer"},
        "starting_city_impact": {"type": "integer"},
        "starting_clue_mastery": {"type": "integer"},
    },
    "required": [
        "cases", "npcs",
        "starting_lantern_understanding", "starting_access", "starting_reputation",
        "starting_leverage", "starting_city_impact", "starting_clue_mastery",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class CitySeedGenerationRequest:
    request_id: str
    concept: str = ""

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must be non-empty")


class CitySeedGenerator:
    """Two-phase LLM-based generator for CitySeedDocument."""

    def __init__(self, llm_client: SupportsJSONGeneration) -> None:
        if not isinstance(llm_client, SupportsJSONGeneration):
            raise TypeError("llm_client must provide a generate_json method")
        self._llm = llm_client

    def generate(
        self,
        request: CitySeedGenerationRequest,
        on_progress: Callable[[str], None] | None = None,
    ) -> CitySeedDocument:
        def _emit(msg: str) -> None:
            if on_progress is not None:
                on_progress(msg)

        _emit("[seed] Phase 1/2 — city framework (identity, districts, factions, lantern)…")
        framework = self._generate_framework(request)
        district_ids = [str(d.get("id", "")) for d in framework.get("districts", [])]
        faction_ids = [str(f.get("id", "")) for f in framework.get("factions", [])]
        city_name = framework.get("city_name", "?")
        _emit(
            f"[seed]   city: {city_name}"
            f"  |  districts: {len(district_ids)}"
            f"  |  factions: {len(faction_ids)}"
        )

        _emit("[seed] Phase 2/2 — cases and NPCs…")
        cases_npcs = self._generate_cases_npcs(request, district_ids, faction_ids)
        n_cases = len(cases_npcs.get("cases", []))
        n_npcs = len(cases_npcs.get("npcs", []))
        _emit(f"[seed]   cases: {n_cases}  |  NPCs: {n_npcs}")

        _emit("[seed] Validating seed…")
        payload = _assemble(framework, cases_npcs)
        try:
            doc = validate_city_seed(payload)
        except Exception as exc:
            raise CitySeedGenerationError(f"Seed validation failed: {exc}") from exc
        _emit("[seed] Seed validated.")
        return doc

    # ── Phase 1 ───────────────────────────────────────────────────────────────

    def _generate_framework(self, request: CitySeedGenerationRequest) -> dict[str, Any]:
        concept_line = f"\nCity concept: {request.concept}\n" if request.concept else ""
        system = (
            "You are generating a city seed for Lantern City, a noir investigative RPG. "
            "Lanterns control memory and truth — each city built on this system is distinct. "
            "Return valid JSON only. No markdown, no explanation."
        )
        user = (
            f"Generate the city framework for a new Lantern City game instance.{concept_line}\n"
            "Requirements:\n"
            "- Give the city a distinct name (not 'Lantern City')\n"
            "- 3–6 districts, each with a distinct role and lantern condition\n"
            "- 2–3 factions with conflicting hidden goals\n"
            "- District IDs: snake_case starting with district_\n"
            "- Faction IDs: snake_case starting with faction_\n"
            "- influence_by_district: every faction must list every district ID\n"
            "- tension_map keys: 'faction_a_id|faction_b_id' format\n"
            "- lantern_condition_distribution values must sum to exactly 1.0\n"
            "- stability_baseline: 0.0–1.0 per district\n"
            "- dominant_mood: 2–4 evocative words\n"
        )
        try:
            return self._llm.generate_json(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.65,
                max_tokens=2200,
                schema=_FRAMEWORK_SCHEMA,
            )
        except Exception as exc:
            raise CitySeedGenerationError(f"Framework generation failed: {exc}") from exc

    # ── Phase 2 ───────────────────────────────────────────────────────────────

    def _generate_cases_npcs(
        self,
        request: CitySeedGenerationRequest,
        district_ids: list[str],
        faction_ids: list[str],
    ) -> dict[str, Any]:
        districts_block = "\n".join(f"  - {did}" for did in district_ids)
        factions_block = "\n".join(f"  - {fid}" for fid in faction_ids)
        concept_line = f"\nCity concept: {request.concept}\n" if request.concept else ""
        system = (
            "You are generating starting cases and NPCs for a Lantern City investigation game. "
            "Return valid JSON only."
        )
        user = (
            f"Generate 1 starting investigation case and 4–10 NPCs.{concept_line}\n\n"
            f"Valid district IDs (use ONLY these):\n{districts_block}\n\n"
            f"Valid faction IDs (use ONLY these):\n{factions_block}\n\n"
            "Requirements:\n"
            "- case.id: snake_case starting with case_\n"
            "- case.involved_district_ids: 1–3 IDs from the valid district list only\n"
            "- case.involved_faction_ids: 1–2 IDs from the valid faction list only\n"
            "- case.key_npc_ids: reference the npc IDs you define below\n"
            "- npc.id: snake_case starting with npc_, all unique\n"
            "- npc.district_id: must be from the valid district list only\n"
            "- npc.location_id: always use 'location_tbd'\n"
            "- Spread NPCs across at least 2 districts\n"
            "- Include at least 1 informant, 1 gatekeeper, 1 authority\n"
            "- Starting scores: integers 0–25 (new investigator, limited knowledge)\n"
        )
        try:
            return self._llm.generate_json(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.55,
                max_tokens=2200,
                schema=_CASES_NPCS_SCHEMA,
            )
        except Exception as exc:
            raise CitySeedGenerationError(f"Cases/NPCs generation failed: {exc}") from exc


# ── Assembly ──────────────────────────────────────────────────────────────────

def _resolve_id(raw: str, valid_ids: list[str], prefix: str) -> str | None:
    """Try to map *raw* to one of *valid_ids*.

    Attempts:
    1. Exact match.
    2. Add missing prefix.
    3. Remove extra prefix then re-add correct one.
    4. Substring match: the raw value (stripped of prefix) appears in a valid ID, or vice-versa.
    Returns None if no match is found.
    """
    if raw in valid_ids:
        return raw

    # Try adding prefix
    candidate = prefix + raw if not raw.startswith(prefix) else raw
    if candidate in valid_ids:
        return candidate

    # Strip any existing prefix and compare slugs
    raw_slug = raw
    for p in (prefix, "district_", "faction_", "npc_"):
        raw_slug = raw_slug.removeprefix(p)
    raw_slug = raw_slug.lower().replace("-", "_").replace(" ", "_")

    best: str | None = None
    for vid in valid_ids:
        vid_slug = vid.removeprefix(prefix).lower()
        if raw_slug in vid_slug or vid_slug in raw_slug:
            best = vid
            break
    return best


def _fix_faction_influences(
    factions: list[dict[str, Any]],
    district_ids: list[str],
) -> list[dict[str, Any]]:
    """Ensure every faction's influence_by_district uses valid district IDs.

    Unknown keys are fuzzy-matched to real district IDs; districts missing from
    the map are filled with a neutral 0.5 value.
    """
    fixed: list[dict[str, Any]] = []
    for faction in factions:
        raw_influence: dict[str, float] = {
            k: float(v) for k, v in faction.get("influence_by_district", {}).items()
        }
        new_influence: dict[str, float] = {}

        for key, val in raw_influence.items():
            resolved = _resolve_id(key, district_ids, "district_")
            if resolved and resolved not in new_influence:
                new_influence[resolved] = val
            # Duplicate or unresolvable keys are silently dropped

        # Fill any district not covered
        for did in district_ids:
            if did not in new_influence:
                new_influence[did] = 0.5

        new_faction = dict(faction)
        new_faction["influence_by_district"] = new_influence
        fixed.append(new_faction)
    return fixed


def _fix_id_list(id_list: list[str], valid_ids: list[str], prefix: str) -> list[str]:
    """Resolve a list of IDs against valid_ids, dropping unresolvable entries."""
    out: list[str] = []
    for raw in id_list:
        resolved = _resolve_id(raw, valid_ids, prefix)
        if resolved and resolved not in out:
            out.append(resolved)
    return out


def _assemble(framework: dict[str, Any], cases_npcs: dict[str, Any]) -> dict[str, Any]:
    districts = list(framework.get("districts", []))
    factions = list(framework.get("factions", []))
    cases = list(cases_npcs.get("cases", []))
    npcs = list(cases_npcs.get("npcs", []))

    district_ids = [str(d.get("id", "")) for d in districts]
    faction_ids = [str(f.get("id", "")) for f in factions]

    # Normalise cross-references so validation doesn't fail on LLM ID inconsistencies
    factions = _fix_faction_influences(factions, district_ids)

    for case in cases:
        case["involved_district_ids"] = _fix_id_list(
            list(case.get("involved_district_ids", [])), district_ids, "district_"
        ) or district_ids[:1]
        case["involved_faction_ids"] = _fix_id_list(
            list(case.get("involved_faction_ids", [])), faction_ids, "faction_"
        )

    for npc in npcs:
        raw_did = str(npc.get("district_id", ""))
        resolved = _resolve_id(raw_did, district_ids, "district_")
        npc["district_id"] = resolved if resolved else (district_ids[0] if district_ids else raw_did)

    return {
        "schema_version": "1.0",
        "city_identity": {
            "city_name": str(framework.get("city_name", "Unnamed City")),
            "dominant_mood": list(framework.get("dominant_mood", ["uncertain", "grey"])),
            "weather_pattern": list(framework.get("weather_pattern", [])),
            "architectural_style": list(framework.get("architectural_style", [])),
            "economic_character": list(framework.get("economic_character", [])),
            "social_texture": list(framework.get("social_texture", [])),
            "ritual_texture": list(framework.get("ritual_texture", [])),
            "baseline_noise_level": str(framework.get("baseline_noise_level", "medium")),
        },
        "district_configuration": {
            "district_count": len(districts),
            "districts": districts,
        },
        "faction_configuration": {
            "faction_count": len(factions),
            "factions": factions,
            "tension_map": dict(framework.get("tension_map", {})),
        },
        "lantern_configuration": {
            "lantern_system_style": str(framework.get("lantern_system_style", "civic grid")),
            "lantern_ownership_structure": str(framework.get("lantern_ownership_structure", "mixed")),
            "lantern_maintenance_structure": str(framework.get("lantern_maintenance_structure", "civic engineers")),
            "lantern_condition_distribution": _normalize_distribution(
                framework.get("lantern_condition_distribution", {})
            ),
            "lantern_reach_profile": str(framework.get("lantern_reach_profile", "district-wide")),
            "lantern_social_effect_profile": list(framework.get("lantern_social_effect_profile", [])),
            "lantern_memory_effect_profile": list(framework.get("lantern_memory_effect_profile", [])),
            "lantern_tampering_probability": _clamp_float(framework.get("lantern_tampering_probability", 0.2)),
        },
        "missingness_configuration": {
            "missingness_pressure": _clamp_float(framework.get("missingness_pressure", 0.4)),
            "missingness_scope": str(framework.get("missingness_scope", "records first")),
            "missingness_visibility": str(framework.get("missingness_visibility", "known-but-denied")),
            "missingness_style": str(framework.get("missingness_style", "edited records")),
            "missingness_targets": list(framework.get("missingness_targets", [])),
            "missingness_risk_level": str(framework.get("missingness_risk_level", "medium")),
        },
        "case_configuration": {
            "starting_case_count": len(cases),
            "cases": cases,
        },
        "npc_configuration": {
            "tracked_npc_count": len(npcs),
            "npcs": npcs,
        },
        "progression_start_state": {
            "starting_lantern_understanding": _clamp_int(cases_npcs.get("starting_lantern_understanding", 15)),
            "starting_access": _clamp_int(cases_npcs.get("starting_access", 10)),
            "starting_reputation": _clamp_int(cases_npcs.get("starting_reputation", 12)),
            "starting_leverage": _clamp_int(cases_npcs.get("starting_leverage", 5)),
            "starting_city_impact": _clamp_int(cases_npcs.get("starting_city_impact", 2)),
            "starting_clue_mastery": _clamp_int(cases_npcs.get("starting_clue_mastery", 15)),
        },
        "tone_and_difficulty": {
            "story_density": str(framework.get("story_density", "medium")),
            "mystery_complexity": str(framework.get("mystery_complexity", "medium")),
            "social_resistance": str(framework.get("social_resistance", "medium")),
            "investigation_pace": str(framework.get("investigation_pace", "deliberate")),
            "consequence_severity": str(framework.get("consequence_severity", "medium")),
            "revelation_delay": str(framework.get("revelation_delay", "gradual")),
            "narrative_strangeness": str(framework.get("narrative_strangeness", "grounded")),
        },
    }


def _normalize_distribution(dist: Any) -> dict[str, float]:
    states = ["bright", "dim", "flickering", "extinguished", "altered"]
    values: dict[str, float] = {}
    if isinstance(dist, dict):
        for s in states:
            try:
                values[s] = max(0.0, float(dist.get(s, 0.0)))
            except (TypeError, ValueError):
                values[s] = 0.0
    total = sum(values.values())
    if total <= 0:
        return {"bright": 0.40, "dim": 0.35, "flickering": 0.15, "extinguished": 0.05, "altered": 0.05}
    return {s: round(v / total, 4) for s, v in values.items()}


def _clamp_float(v: Any) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.2


def _clamp_int(v: Any) -> int:
    try:
        return max(0, min(100, int(v)))
    except (TypeError, ValueError):
        return 10


__all__ = [
    "CitySeedGenerationError",
    "CitySeedGenerationRequest",
    "CitySeedGenerator",
    "SupportsJSONGeneration",
]
