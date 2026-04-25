from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from lantern_city.active_slice import ActiveSlice
from lantern_city.app import _MODEL_QUALITY_PROBE_SCHEMA, _model_probe_messages
from lantern_city.generation.case_generation import (
    CaseGenerationRequest,
    CaseGenerationResult,
    CaseGenerator,
)
from lantern_city.generation.city_seed import (
    CitySeedGenerationRequest,
    CitySeedGenerator,
    _assemble,
)
from lantern_city.generation.npc_response import (
    NPCResponseGenerationRequest,
    NPCResponseGenerationResult,
    NPCResponseGenerator,
    sanitize_npc_response_payload,
)
from lantern_city.llm_client import OpenAICompatibleConfig, OpenAICompatibleLLMClient
from lantern_city.models import (
    ActiveWorkingSet,
    CaseState,
    CityState,
    ClueState,
    DistrictState,
    FactionState,
    LocationState,
    NPCState,
    PlayerProgressState,
    PlayerRequest,
    SceneState,
    ScoreTier,
)
from lantern_city.seed_schema import validate_city_seed


PromptStageStatus = Literal["pass", "warning", "fail"]


@dataclass(slots=True)
class PromptCheckStageResult:
    name: str
    status: PromptStageStatus
    elapsed_seconds: float
    summary: str
    sample: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptDiagnosticsReport:
    base_url: str
    model: str
    concept: str
    stages: list[PromptCheckStageResult]

    @property
    def overall_status(self) -> PromptStageStatus:
        if any(stage.status == "fail" for stage in self.stages):
            return "fail"
        if any(stage.status == "warning" for stage in self.stages):
            return "warning"
        return "pass"

    def to_text(self) -> str:
        lines = [
            "=== Prompt Check ===",
            f"Model: {self.model}",
            f"URL: {self.base_url}",
            f"Concept: {self.concept or '(default)'}",
            f"Overall: {self.overall_status}",
            "",
        ]
        for stage in self.stages:
            lines.append(
                f"[{stage.status}] {stage.name} ({stage.elapsed_seconds:.1f}s) — {stage.summary}"
            )
            if stage.sample:
                lines.append(f"  sample: {stage.sample}")
            for warning in stage.warnings:
                lines.append(f"  warning: {warning}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            {
                "base_url": self.base_url,
                "model": self.model,
                "concept": self.concept,
                "overall_status": self.overall_status,
                "stages": [asdict(stage) for stage in self.stages],
            },
            indent=2,
            ensure_ascii=False,
        )

    def write_json(self, path: str | Path) -> Path:
        out = Path(path)
        out.write_text(self.to_json(), encoding="utf-8")
        return out


def run_prompt_diagnostics(
    *,
    llm_config: OpenAICompatibleConfig,
    concept: str = "",
    llm_client: OpenAICompatibleLLMClient | None = None,
) -> PromptDiagnosticsReport:
    client = llm_client or OpenAICompatibleLLMClient(llm_config)
    owns_client = llm_client is None
    try:
        framework_result, framework_payload, district_ids, faction_ids = _run_city_framework_check(
            client, concept=concept
        )
        stages: list[PromptCheckStageResult] = [
            _run_startup_probe_check(client),
            framework_result,
        ]
        stages.append(
            _run_city_seed_cases_check(
                client,
                concept=concept,
                framework_payload=framework_payload,
                district_ids=district_ids,
                faction_ids=faction_ids,
            )
        )
        stages.append(_run_case_generation_check(client))
        stages.append(_run_npc_response_check(client))
        return PromptDiagnosticsReport(
            base_url=llm_config.base_url,
            model=llm_config.model,
            concept=concept,
            stages=stages,
        )
    finally:
        if owns_client:
            client.close()


def _stage_status(*, elapsed: float, warnings: list[str], failed: bool) -> PromptStageStatus:
    if failed:
        return "fail"
    if elapsed > 20.0 and "slow response" not in warnings:
        warnings.append("slow response")
    return "warning" if warnings else "pass"


def _shorten(text: str, max_length: int = 160) -> str:
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _run_startup_probe_check(client: OpenAICompatibleLLMClient) -> PromptCheckStageResult:
    started = perf_counter()
    try:
        payload = client.generate_json(
            messages=_model_probe_messages(),
            temperature=0.1,
            max_tokens=600,
            schema=_MODEL_QUALITY_PROBE_SCHEMA,
        )
        payload = sanitize_npc_response_payload(payload)
        result = NPCResponseGenerationResult.model_validate(payload)
        elapsed = perf_counter() - started
        warnings: list[str] = []
        if result.confidence < 0.35:
            warnings.append("low confidence probe response")
        return PromptCheckStageResult(
            name="startup_probe",
            status=_stage_status(elapsed=elapsed, warnings=warnings, failed=False),
            elapsed_seconds=elapsed,
            summary=f"NPC probe validated with confidence {result.confidence:.2f}",
            sample=_shorten(result.cacheable_text.npc_line),
            warnings=warnings,
        )
    except Exception as exc:
        elapsed = perf_counter() - started
        return PromptCheckStageResult(
            name="startup_probe",
            status="fail",
            elapsed_seconds=elapsed,
            summary=f"probe failed: {exc}",
        )


def _run_city_framework_check(
    client: OpenAICompatibleLLMClient,
    *,
    concept: str,
) -> tuple[PromptCheckStageResult, dict[str, Any] | None, list[str], list[str]]:
    started = perf_counter()
    request = CitySeedGenerationRequest(request_id="prompt_check_seed", concept=concept)
    generator = CitySeedGenerator(client)
    try:
        framework = generator._generate_framework(request)
        elapsed = perf_counter() - started
        district_ids = [str(item.get("id", "")) for item in framework.get("districts", [])]
        faction_ids = [str(item.get("id", "")) for item in framework.get("factions", [])]
        city_name = str(framework.get("city_name", "?"))
        warnings: list[str] = []
        return (
            PromptCheckStageResult(
                name="city_framework",
                status=_stage_status(elapsed=elapsed, warnings=warnings, failed=False),
                elapsed_seconds=elapsed,
                summary=f"{city_name} / {len(district_ids)} districts / {len(faction_ids)} factions",
                sample=_shorten(", ".join(item.get("name", "?") for item in framework.get("districts", [])[:3])),
                warnings=warnings,
            ),
            framework,
            district_ids,
            faction_ids,
        )
    except Exception as exc:
        elapsed = perf_counter() - started
        return (
            PromptCheckStageResult(
                name="city_framework",
                status="fail",
                elapsed_seconds=elapsed,
                summary=f"framework generation failed: {exc}",
            ),
            None,
            [],
            [],
        )


def _run_city_seed_cases_check(
    client: OpenAICompatibleLLMClient,
    *,
    concept: str,
    framework_payload: dict[str, Any] | None,
    district_ids: list[str],
    faction_ids: list[str],
) -> PromptCheckStageResult:
    if framework_payload is None:
        return PromptCheckStageResult(
            name="city_seed_cases_npcs",
            status="fail",
            elapsed_seconds=0.0,
            summary="skipped because city framework failed",
        )
    started = perf_counter()
    request = CitySeedGenerationRequest(request_id="prompt_check_seed", concept=concept)
    generator = CitySeedGenerator(client)
    try:
        cases_npcs = generator._generate_cases_npcs(request, district_ids, faction_ids)
        assembled = _assemble(framework_payload, cases_npcs)
        seed = validate_city_seed(assembled)
        elapsed = perf_counter() - started
        warnings: list[str] = []
        return PromptCheckStageResult(
            name="city_seed_cases_npcs",
            status=_stage_status(elapsed=elapsed, warnings=warnings, failed=False),
            elapsed_seconds=elapsed,
            summary=(
                f"{len(seed.case_configuration.cases)} starting case(s) / "
                f"{len(seed.npc_configuration.npcs)} NPC(s) / "
                "assembled seed validated"
            ),
            sample=_shorten(", ".join(npc.id for npc in seed.npc_configuration.npcs[:4])),
            warnings=warnings,
        )
    except Exception as exc:
        elapsed = perf_counter() - started
        return PromptCheckStageResult(
            name="city_seed_cases_npcs",
            status="fail",
            elapsed_seconds=elapsed,
            summary=f"cases/NPCs generation failed: {exc}",
        )


def _run_case_generation_check(client: OpenAICompatibleLLMClient) -> PromptCheckStageResult:
    started = perf_counter()
    try:
        request = _synthetic_case_generation_request()
        generator = CaseGenerator(client)
        result = generator.generate(request)
        elapsed = perf_counter() - started
        warnings: list[str] = []
        return PromptCheckStageResult(
            name="latent_case_generation",
            status=_stage_status(elapsed=elapsed, warnings=warnings, failed=False),
            elapsed_seconds=elapsed,
            summary=(
                f"{result.title} / {result.case_type} / "
                f"{len(result.npc_specs)} NPCs / {len(result.clue_specs)} clues"
            ),
            sample=_shorten(result.opening_hook),
            warnings=warnings,
        )
    except Exception as exc:
        elapsed = perf_counter() - started
        return PromptCheckStageResult(
            name="latent_case_generation",
            status="fail",
            elapsed_seconds=elapsed,
            summary=f"case generation failed: {exc}",
        )


def _run_npc_response_check(client: OpenAICompatibleLLMClient) -> PromptCheckStageResult:
    started = perf_counter()
    try:
        request = _synthetic_npc_response_request()
        generator = NPCResponseGenerator(client)
        result = generator.generate(request)
        elapsed = perf_counter() - started
        warnings: list[str] = []
        if result.confidence < 0.35:
            warnings.append("low confidence npc response")
        return PromptCheckStageResult(
            name="npc_response_generation",
            status=_stage_status(elapsed=elapsed, warnings=warnings, failed=False),
            elapsed_seconds=elapsed,
            summary=(
                f"{result.structured_updates.dialogue_act} / "
                f"{result.structured_updates.npc_stance} / confidence {result.confidence:.2f}"
            ),
            sample=_shorten(result.cacheable_text.npc_line),
            warnings=warnings,
        )
    except Exception as exc:
        elapsed = perf_counter() - started
        return PromptCheckStageResult(
            name="npc_response_generation",
            status="fail",
            elapsed_seconds=elapsed,
            summary=f"npc response generation failed: {exc}",
        )


def _synthetic_case_generation_request() -> CaseGenerationRequest:
    city = CityState(
        id="city_prompt_check",
        created_at="turn_0",
        updated_at="turn_0",
        city_seed_id="seed_prompt_check",
        global_tension=0.42,
        missingness_pressure=0.58,
        district_ids=["district_old_quarter", "district_lantern_ward", "district_the_docks"],
        faction_ids=["faction_memory_keepers", "faction_council_lights"],
    )
    districts = [
        DistrictState(
            id="district_old_quarter",
            created_at="turn_0",
            updated_at="turn_0",
            name="Old Quarter",
            tone="wet archives and guarded clerks",
            lantern_condition="dim",
            stability=0.47,
            current_access_level="restricted",
            active_problems=["records drifting out of sync", "quiet witness pressure"],
            summary_cache={
                "social_rule": "speak carefully and never accuse without support",
                "investigation_pressure": "contradiction",
            },
        ),
        DistrictState(
            id="district_lantern_ward",
            created_at="turn_0",
            updated_at="turn_0",
            name="Lantern Ward",
            tone="official scrutiny and calibrated procedure",
            lantern_condition="bright",
            stability=0.72,
            current_access_level="trusted",
            active_problems=["official access tightening"],
            summary_cache={
                "social_rule": "follow the formal path or lose it",
                "investigation_pressure": "institutional denial",
            },
        ),
        DistrictState(
            id="district_the_docks",
            created_at="turn_0",
            updated_at="turn_0",
            name="The Docks",
            tone="cargo noise and quiet side deals",
            lantern_condition="flickering",
            stability=0.39,
            current_access_level="public",
            active_problems=["missing manifests", "night traffic rerouted"],
            summary_cache={
                "social_rule": "nothing moves without a witness or a bribe",
                "investigation_pressure": "hidden routes",
            },
        ),
    ]
    factions = [
        FactionState(
            id="faction_memory_keepers",
            created_at="turn_0",
            updated_at="turn_0",
            name="Memory Keepers",
            public_goal="preserve continuity",
            hidden_goal="control the official record",
            influence_by_district={
                "district_old_quarter": 0.8,
                "district_lantern_ward": 0.5,
                "district_the_docks": 0.2,
            },
            tension_with_other_factions={"faction_council_lights": 0.7},
            attitude_toward_player="guarded",
            active_plans=["procedural delay"],
            known_assets=["archives", "certification desks"],
        ),
        FactionState(
            id="faction_council_lights",
            created_at="turn_0",
            updated_at="turn_0",
            name="Council of Lights",
            public_goal="keep the city orderly",
            hidden_goal="smother investigations that expose civic weakness",
            influence_by_district={
                "district_old_quarter": 0.3,
                "district_lantern_ward": 0.9,
                "district_the_docks": 0.4,
            },
            tension_with_other_factions={"faction_memory_keepers": 0.7},
            attitude_toward_player="neutral",
            active_plans=["tighten access"],
            known_assets=["permits", "watch patrols"],
        ),
    ]
    progress = PlayerProgressState(
        id="progress_prompt_check",
        created_at="turn_0",
        updated_at="turn_0",
        lantern_understanding=ScoreTier(score=8, tier="Novice"),
        access=ScoreTier(score=10, tier="Restricted"),
        reputation=ScoreTier(score=7, tier="Known"),
        leverage=ScoreTier(score=6, tier="Limited"),
        city_impact=ScoreTier(score=4, tier="Unknown"),
        clue_mastery=ScoreTier(score=8, tier="Novice"),
    )
    return CaseGenerationRequest(
        request_id="prompt_check_case_001",
        city=city,
        factions=factions,
        districts=districts,
        progress=progress,
        existing_case_types=["records tampering"],
        existing_npc_names=["Ila Venn", "Sered Marr"],
    )


def _synthetic_npc_response_request() -> NPCResponseGenerationRequest:
    city = CityState(
        id="city_prompt_check",
        created_at="turn_0",
        updated_at="turn_0",
        city_seed_id="seed_prompt_check",
    )
    district = DistrictState(
        id="district_old_quarter",
        created_at="turn_0",
        updated_at="turn_0",
        name="Old Quarter",
        tone="hushed and procedural",
        lantern_condition="flickering",
        visible_locations=["location_archive_steps", "location_registry_annex"],
    )
    location = LocationState(
        id="location_archive_steps",
        created_at="turn_0",
        updated_at="turn_0",
        district_id=district.id,
        name="Archive Steps",
        location_type="archive",
        known_npc_ids=["npc_ila_venn"],
        clue_ids=["clue_altered_ledger"],
    )
    scene = SceneState(
        id="scene_archive_talk",
        created_at="turn_0",
        updated_at="turn_0",
        scene_type="conversation",
        location_id=location.id,
        participating_npc_ids=["npc_ila_venn"],
        immediate_goal="Find out who altered the ledger.",
    )
    npc = NPCState(
        id="npc_ila_venn",
        created_at="turn_0",
        updated_at="turn_0",
        name="Ila Venn",
        role_category="gatekeeper",
        district_id=district.id,
        location_id=location.id,
        public_identity="Keeps the lantern records for the ward.",
        hidden_objective="Keep the annex clear of investigation.",
        current_objective="Deflect questions about the altered ledger.",
        trust_in_player=0.15,
        fear=0.42,
        suspicion=0.55,
        loyalty="faction_memory_keepers",
        known_clue_ids=["clue_altered_ledger"],
    )
    clue = ClueState(
        id="clue_altered_ledger",
        created_at="turn_0",
        updated_at="turn_0",
        source_type="document",
        source_id=location.id,
        clue_text="The ledger shows two different hands on the same correction line.",
        reliability="credible",
        related_case_ids=["case_missing_ledger"],
    )
    case = CaseState(
        id="case_missing_ledger",
        created_at="turn_0",
        updated_at="turn_0",
        title="Missing Ledger",
        case_type="records tampering",
        status="active",
        involved_district_ids=[district.id],
        involved_npc_ids=[npc.id],
        known_clue_ids=[clue.id],
        objective_summary="Work out who altered the ledger after dusk.",
    )
    working_set = ActiveWorkingSet(
        id="aws_prompt_check",
        created_at="turn_0",
        updated_at="turn_0",
        city_id=city.id,
        district_id=district.id,
        location_id=location.id,
        case_id=case.id,
        scene_id=scene.id,
        npc_ids=[npc.id],
        clue_ids=[clue.id],
    )
    active_slice = ActiveSlice(
        city=city,
        working_set=working_set,
        district=district,
        location=location,
        scene=scene,
        npcs=[npc],
        clues=[clue],
        case=case,
    )
    request = PlayerRequest(
        id="req_prompt_check_npc_001",
        created_at="turn_0",
        updated_at="turn_0",
        player_id="player_001",
        intent="talk_to_npc",
        target_id=npc.id,
        location_id=location.id,
        case_id=case.id,
        scene_id=scene.id,
        input_text="Ask who altered the ledger after dusk.",
    )
    progress = PlayerProgressState(
        id="progress_prompt_check",
        created_at="turn_0",
        updated_at="turn_0",
        lantern_understanding=ScoreTier(score=8, tier="Novice"),
        access=ScoreTier(score=10, tier="Restricted"),
        reputation=ScoreTier(score=7, tier="Known"),
        leverage=ScoreTier(score=6, tier="Limited"),
        city_impact=ScoreTier(score=4, tier="Unknown"),
        clue_mastery=ScoreTier(score=8, tier="Novice"),
    )
    faction = FactionState(
        id="faction_memory_keepers",
        created_at="turn_0",
        updated_at="turn_0",
        name="Memory Keepers",
        public_goal="preserve continuity",
        hidden_goal="control the official record",
        attitude_toward_player="guarded",
        active_plans=["procedural delay"],
    )
    return NPCResponseGenerationRequest(
        request_id="req_prompt_check_npc_001",
        active_slice=active_slice,
        player_request=request,
        progress=progress,
        loyalty_faction=faction,
    )


__all__ = [
    "PromptCheckStageResult",
    "PromptDiagnosticsReport",
    "run_prompt_diagnostics",
]
