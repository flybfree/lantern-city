from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list[JSONValue] | dict[str, JSONValue]
type JSONObject = dict[str, JSONValue]


class LanternCityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RuntimeModel(LanternCityModel):
    id: str
    type: str
    version: int = 1
    created_at: str
    updated_at: str


class ScoreTier(LanternCityModel):
    score: int
    tier: str


class RelationshipSnapshot(LanternCityModel):
    trust: float = 0.0
    suspicion: float = 0.0
    fear: float = 0.0
    status: str = ""
    last_updated_at: str = ""


class CitySeed(RuntimeModel):
    type: Literal["CitySeed"] = "CitySeed"
    city_premise: str
    dominant_mood: list[str] = Field(default_factory=list)
    district_ids: list[str] = Field(default_factory=list)
    faction_ids: list[str] = Field(default_factory=list)
    starting_cases: list[str] = Field(default_factory=list)
    initial_missingness_pressure: float | None = None
    initial_lantern_profile: dict[str, str] = Field(default_factory=dict)
    key_npc_ids: list[str] = Field(default_factory=list)


class CityState(RuntimeModel):
    type: Literal["CityState"] = "CityState"
    city_seed_id: str
    time_index: int = 0
    global_tension: float = 0.0
    civic_trust: float = 0.0
    missingness_pressure: float = 0.0
    active_case_ids: list[str] = Field(default_factory=list)
    district_ids: list[str] = Field(default_factory=list)
    faction_ids: list[str] = Field(default_factory=list)
    player_presence_level: float = 0.0
    summary_cache: dict[str, str] = Field(default_factory=dict)


class DistrictState(RuntimeModel):
    type: Literal["DistrictState"] = "DistrictState"
    name: str
    tone: str = ""
    stability: float = 0.0
    lantern_condition: str = "unknown"
    governing_power: str | None = None
    active_problems: list[str] = Field(default_factory=list)
    visible_locations: list[str] = Field(default_factory=list)
    hidden_locations: list[str] = Field(default_factory=list)
    relevant_npc_ids: list[str] = Field(default_factory=list)
    rumor_pool: list[str] = Field(default_factory=list)
    current_access_level: str = "unknown"
    summary_cache: dict[str, str] = Field(default_factory=dict)


class LocationState(RuntimeModel):
    type: Literal["LocationState"] = "LocationState"
    district_id: str
    name: str
    location_type: str
    access_state: str = "unknown"
    known_npc_ids: list[str] = Field(default_factory=list)
    hidden_feature_ids: list[str] = Field(default_factory=list)
    clue_ids: list[str] = Field(default_factory=list)
    scene_objects: list[str] = Field(default_factory=list)
    lantern_effects: dict[str, float] = Field(default_factory=dict)
    description_cache: dict[str, str] = Field(default_factory=dict)


class NPCState(RuntimeModel):
    type: Literal["NPCState"] = "NPCState"
    name: str
    role_category: str
    district_id: str | None = None
    location_id: str | None = None
    public_identity: str = ""
    hidden_objective: str = ""
    current_objective: str = ""
    trust_in_player: float = 0.0
    fear: float = 0.0
    suspicion: float = 0.0
    loyalty: str | None = None
    known_clue_ids: list[str] = Field(default_factory=list)
    known_promises: list[str] = Field(default_factory=list)
    relationship_flags: list[str] = Field(default_factory=list)
    relationships: dict[str, RelationshipSnapshot] = Field(default_factory=dict)
    memory_log: list[JSONObject] = Field(default_factory=list)
    schedule_anchor: str = ""
    offscreen_state: str = "idle"
    recent_events: list[str] = Field(default_factory=list)
    player_flags: list[str] = Field(default_factory=list)
    relevance_rating: float = 0.0


class FactionState(RuntimeModel):
    type: Literal["FactionState"] = "FactionState"
    name: str
    public_goal: str = ""
    hidden_goal: str = ""
    influence_by_district: dict[str, float] = Field(default_factory=dict)
    tension_with_other_factions: dict[str, float] = Field(default_factory=dict)
    attitude_toward_player: str = "neutral"
    known_assets: list[str] = Field(default_factory=list)
    known_losses: list[str] = Field(default_factory=list)
    active_plans: list[str] = Field(default_factory=list)
    summary_cache: dict[str, str] = Field(default_factory=dict)


class LanternState(RuntimeModel):
    type: Literal["LanternState"] = "LanternState"
    scope_type: str
    scope_id: str
    owner_faction: str | None = None
    maintainer_group: str | None = None
    condition_state: str = "unknown"
    reach_scope_notes: str = ""
    social_effects: list[str] = Field(default_factory=list)
    memory_effects: list[str] = Field(default_factory=list)
    access_effects: list[str] = Field(default_factory=list)
    anomaly_flags: list[str] = Field(default_factory=list)


class CaseState(RuntimeModel):
    type: Literal["CaseState"] = "CaseState"
    title: str
    case_type: str
    status: str
    involved_district_ids: list[str] = Field(default_factory=list)
    involved_npc_ids: list[str] = Field(default_factory=list)
    involved_faction_ids: list[str] = Field(default_factory=list)
    known_clue_ids: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    objective_summary: str = ""
    resolution_summary: str | None = None
    fallout_summary: str | None = None
    pressure_level: str = "low"
    time_since_last_progress: int = 0
    offscreen_risk_flags: list[str] = Field(default_factory=list)
    active_resolution_window: str = "open"
    district_effects: list[str] = Field(default_factory=list)
    npc_pressure_targets: list[str] = Field(default_factory=list)
    # Generated case fields
    discovery_hook: str = ""
    hook_npc_id: str = ""  # NPC who introduces the case through conversation; empty = district-entry trigger
    resolution_conditions: list[JSONObject] = Field(default_factory=list)


class SceneState(RuntimeModel):
    type: Literal["SceneState"] = "SceneState"
    case_id: str | None = None
    scene_type: str
    location_id: str | None = None
    participating_npc_ids: list[str] = Field(default_factory=list)
    immediate_goal: str = ""
    current_prompt_state: str = ""
    scene_clue_ids: list[str] = Field(default_factory=list)
    scene_tension: float = 0.0
    scene_outcome: str | None = None


class ClueState(RuntimeModel):
    type: Literal["ClueState"] = "ClueState"
    source_type: str
    source_id: str
    clue_text: str
    reliability: str = "unknown"
    tags: list[str] = Field(default_factory=list)
    related_npc_ids: list[str] = Field(default_factory=list)
    related_case_ids: list[str] = Field(default_factory=list)
    related_district_ids: list[str] = Field(default_factory=list)
    status: str = "new"


class PlayerProgressState(RuntimeModel):
    type: Literal["PlayerProgressState"] = "PlayerProgressState"
    lantern_understanding: ScoreTier = Field(
        default_factory=lambda: ScoreTier(score=0, tier="Unknown")
    )
    access: ScoreTier = Field(default_factory=lambda: ScoreTier(score=0, tier="Unknown"))
    reputation: ScoreTier = Field(default_factory=lambda: ScoreTier(score=0, tier="Unknown"))
    leverage: ScoreTier = Field(default_factory=lambda: ScoreTier(score=0, tier="Unknown"))
    city_impact: ScoreTier = Field(default_factory=lambda: ScoreTier(score=0, tier="Unknown"))
    clue_mastery: ScoreTier = Field(default_factory=lambda: ScoreTier(score=0, tier="Unknown"))


class PlayerRequest(RuntimeModel):
    type: Literal["PlayerRequest"] = "PlayerRequest"
    player_id: str
    intent: str
    target_id: str | None = None
    location_id: str | None = None
    case_id: str | None = None
    scene_id: str | None = None
    input_text: str = ""
    context_refs: JSONObject = Field(default_factory=dict)


class GenerationJob(RuntimeModel):
    type: Literal["GenerationJob"] = "GenerationJob"
    job_kind: str
    priority: str = "normal"
    status: str = "queued"
    input_refs: JSONObject = Field(default_factory=dict)
    required_outputs: list[str] = Field(default_factory=list)
    cached_output_id: str | None = None


class GeneratedOutput(RuntimeModel):
    type: Literal["GeneratedOutput"] = "GeneratedOutput"
    source_job_id: str
    output_kind: str
    text: str = ""
    structured_updates: JSONObject = Field(default_factory=dict)


class PlayerResponse(RuntimeModel):
    type: Literal["PlayerResponse"] = "PlayerResponse"
    request_id: str
    narrative_text: str = ""
    state_changes: list[JSONObject] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ActiveWorkingSet(RuntimeModel):
    type: Literal["ActiveWorkingSet"] = "ActiveWorkingSet"
    city_id: str
    district_id: str | None = None
    location_id: str | None = None
    case_id: str | None = None
    scene_id: str | None = None
    npc_ids: list[str] = Field(default_factory=list)
    clue_ids: list[str] = Field(default_factory=list)
    known_case_ids: list[str] = Field(default_factory=list)
    visited_district_ids: list[str] = Field(default_factory=list)
    last_meaningful_action_at: str = ""
    cached_summaries: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "ActiveWorkingSet",
    "CaseState",
    "CitySeed",
    "CityState",
    "ClueState",
    "DistrictState",
    "FactionState",
    "GeneratedOutput",
    "GenerationJob",
    "JSONObject",
    "JSONScalar",
    "JSONValue",
    "LanternCityModel",
    "LanternState",
    "LocationState",
    "NPCState",
    "PlayerProgressState",
    "PlayerRequest",
    "PlayerResponse",
    "RelationshipSnapshot",
    "RuntimeModel",
    "SceneState",
    "ScoreTier",
]
