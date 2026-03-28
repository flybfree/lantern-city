from __future__ import annotations

from math import isclose
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

NoiseLevel = Literal["low", "medium", "high"]
LanternStateValue = Literal["bright", "dim", "flickering", "extinguished", "altered"]
RiskLevel = Literal["low", "medium", "high"]


class SeedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CityIdentity(SeedModel):
    city_name: str
    dominant_mood: list[str]
    weather_pattern: list[str] = Field(default_factory=list)
    architectural_style: list[str] = Field(default_factory=list)
    economic_character: list[str] = Field(default_factory=list)
    social_texture: list[str] = Field(default_factory=list)
    ritual_texture: list[str] = Field(default_factory=list)
    baseline_noise_level: NoiseLevel

    @model_validator(mode="after")
    def validate_city_identity(self) -> CityIdentity:
        if not self.city_name.strip():
            raise ValueError("city_name must be non-empty")

        if not 2 <= len(self.dominant_mood) <= 4:
            raise ValueError("dominant_mood must contain 2 to 4 entries")

        for mood in self.dominant_mood:
            if not mood.strip():
                raise ValueError("dominant_mood entries must be non-empty strings")

        return self


class District(SeedModel):
    id: str
    name: str
    role: str
    stability_baseline: float = Field(ge=0.0, le=1.0)
    lantern_state: LanternStateValue
    access_pattern: str
    hidden_location_density: str


class DistrictConfiguration(SeedModel):
    district_count: int = Field(ge=0)
    districts: list[District]

    @model_validator(mode="after")
    def validate_districts(self) -> DistrictConfiguration:
        if self.district_count != len(self.districts):
            raise ValueError("district_count must match the number of districts")

        district_ids = [district.id for district in self.districts]
        if len(set(district_ids)) != len(district_ids):
            raise ValueError("each district must have a unique district id")

        district_names = [district.name for district in self.districts]
        if len(set(district_names)) != len(district_names):
            raise ValueError("each district must have a unique district name")

        return self


class Faction(SeedModel):
    id: str
    name: str
    role: str
    public_goal: str
    hidden_goal: str
    influence_by_district: dict[str, float] = Field(default_factory=dict)
    attitude_toward_player: str


class FactionConfiguration(SeedModel):
    faction_count: int = Field(ge=0)
    factions: list[Faction]
    tension_map: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_factions(self) -> FactionConfiguration:
        if self.faction_count != len(self.factions):
            raise ValueError("faction_count must match the number of factions")

        faction_ids = [faction.id for faction in self.factions]
        if len(set(faction_ids)) != len(faction_ids):
            raise ValueError("each faction must have a unique faction id")

        faction_names = [faction.name for faction in self.factions]
        if len(set(faction_names)) != len(faction_names):
            raise ValueError("each faction must have a unique faction name")

        faction_id_set = set(faction_ids)
        for key in self.tension_map:
            left, separator, right = key.partition("|")
            if not separator or not left or not right:
                raise ValueError("tension_map keys must use faction_a|faction_b format")
            if left == right:
                raise ValueError("tension_map keys must reference two different factions")
            if left not in faction_id_set or right not in faction_id_set:
                raise ValueError(f"tension_map references unknown faction ids: {key}")

        return self


class LanternConfiguration(SeedModel):
    lantern_system_style: str
    lantern_ownership_structure: str
    lantern_maintenance_structure: str
    lantern_condition_distribution: dict[LanternStateValue, float]
    lantern_reach_profile: str
    lantern_social_effect_profile: list[str] = Field(default_factory=list)
    lantern_memory_effect_profile: list[str] = Field(default_factory=list)
    lantern_tampering_probability: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_lantern_configuration(self) -> LanternConfiguration:
        total = sum(self.lantern_condition_distribution.values())
        if not isclose(total, 1.0, abs_tol=0.01):
            raise ValueError(
                "lantern_condition_distribution must sum approximately to 1.0"
            )
        return self


class MissingnessConfiguration(SeedModel):
    missingness_pressure: float = Field(ge=0.0, le=1.0)
    missingness_scope: str
    missingness_visibility: str
    missingness_style: str
    missingness_targets: list[str] = Field(default_factory=list)
    missingness_risk_level: RiskLevel


class CaseSeed(SeedModel):
    id: str
    type: str
    intensity: str
    scope: str
    involved_district_ids: list[str] = Field(default_factory=list)
    involved_faction_ids: list[str] = Field(default_factory=list)
    key_npc_ids: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)


class CaseConfiguration(SeedModel):
    starting_case_count: int = Field(ge=0)
    cases: list[CaseSeed]

    @model_validator(mode="after")
    def validate_cases(self) -> CaseConfiguration:
        if self.starting_case_count != len(self.cases):
            raise ValueError("starting_case_count must match the number of cases")
        return self


class NPCSeed(SeedModel):
    id: str
    name: str
    role_category: str
    district_id: str
    location_id: str
    memory_depth: str
    relationship_density: str
    secrecy_level: str
    mobility_pattern: str
    relevance_level: str


class NPCConfiguration(SeedModel):
    tracked_npc_count: int = Field(ge=0)
    npcs: list[NPCSeed]

    @model_validator(mode="after")
    def validate_npcs(self) -> NPCConfiguration:
        if self.tracked_npc_count != len(self.npcs):
            raise ValueError("tracked_npc_count must match the number of detailed NPC records")

        npc_ids = [npc.id for npc in self.npcs]
        if len(set(npc_ids)) != len(npc_ids):
            raise ValueError("each NPC must have a unique npc id")

        return self


class ProgressionStartState(SeedModel):
    starting_lantern_understanding: int = Field(ge=0, le=100)
    starting_access: int = Field(ge=0, le=100)
    starting_reputation: int = Field(ge=0, le=100)
    starting_leverage: int = Field(ge=0, le=100)
    starting_city_impact: int = Field(ge=0, le=100)
    starting_clue_mastery: int = Field(ge=0, le=100)


class ToneAndDifficulty(SeedModel):
    story_density: str
    mystery_complexity: str
    social_resistance: str
    investigation_pace: str
    consequence_severity: str
    revelation_delay: str
    narrative_strangeness: str


class CitySeedDocument(SeedModel):
    schema_version: str
    city_identity: CityIdentity
    district_configuration: DistrictConfiguration
    faction_configuration: FactionConfiguration
    lantern_configuration: LanternConfiguration
    missingness_configuration: MissingnessConfiguration
    case_configuration: CaseConfiguration
    npc_configuration: NPCConfiguration
    progression_start_state: ProgressionStartState
    tone_and_difficulty: ToneAndDifficulty

    @model_validator(mode="after")
    def validate_cross_references(self) -> CitySeedDocument:
        district_ids = {district.id for district in self.district_configuration.districts}
        faction_ids = {faction.id for faction in self.faction_configuration.factions}
        npc_ids = {npc.id for npc in self.npc_configuration.npcs}

        for faction in self.faction_configuration.factions:
            unknown_districts = set(faction.influence_by_district) - district_ids
            if unknown_districts:
                unknown = ", ".join(sorted(unknown_districts))
                raise ValueError(f"faction influence_by_district references unknown district ids: {unknown}")

        key_npc_anchor_ids: set[str] = set()
        for case in self.case_configuration.cases:
            unknown_districts = set(case.involved_district_ids) - district_ids
            if unknown_districts:
                unknown = ", ".join(sorted(unknown_districts))
                raise ValueError(f"case references unknown district ids: {unknown}")

            unknown_factions = set(case.involved_faction_ids) - faction_ids
            if unknown_factions:
                unknown = ", ".join(sorted(unknown_factions))
                raise ValueError(f"case references unknown faction ids: {unknown}")

            unknown_npcs = set(case.key_npc_ids) - npc_ids
            if unknown_npcs:
                unknown = ", ".join(sorted(unknown_npcs))
                raise ValueError(f"case references unknown npc ids: {unknown}")

            key_npc_anchor_ids.update(case.key_npc_ids)

        for npc in self.npc_configuration.npcs:
            if npc.district_id not in district_ids:
                raise ValueError(f"npc references unknown district id: {npc.district_id}")

        return self


def validate_city_seed(payload: Any) -> CitySeedDocument:
    return CitySeedDocument.model_validate(payload)


__all__ = ["CitySeedDocument", "validate_city_seed", "ValidationError"]
