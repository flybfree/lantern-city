from __future__ import annotations

from math import isclose
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

NoiseLevel = Literal["low", "medium", "high"]
LanternStateValue = Literal["bright", "dim", "flickering", "extinguished", "altered"]
RiskLevel = Literal["low", "medium", "high"]
ALL_LANTERN_STATES = {"bright", "dim", "flickering", "extinguished", "altered"}

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonEmptyStrList = list[NonEmptyStr]


class SeedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CityIdentity(SeedModel):
    city_name: NonEmptyStr
    dominant_mood: NonEmptyStrList
    weather_pattern: NonEmptyStrList = Field(default_factory=list)
    architectural_style: NonEmptyStrList = Field(default_factory=list)
    economic_character: NonEmptyStrList = Field(default_factory=list)
    social_texture: NonEmptyStrList = Field(default_factory=list)
    ritual_texture: NonEmptyStrList = Field(default_factory=list)
    baseline_noise_level: NoiseLevel

    @model_validator(mode="after")
    def validate_city_identity(self) -> CityIdentity:
        if not 2 <= len(self.dominant_mood) <= 4:
            raise ValueError("dominant_mood must contain 2 to 4 entries")

        return self


class District(SeedModel):
    id: NonEmptyStr
    name: NonEmptyStr
    role: NonEmptyStr
    stability_baseline: float = Field(ge=0.0, le=1.0)
    lantern_state: LanternStateValue
    access_pattern: NonEmptyStr
    hidden_location_density: NonEmptyStr


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
    id: NonEmptyStr
    name: NonEmptyStr
    role: NonEmptyStr
    public_goal: NonEmptyStr
    hidden_goal: NonEmptyStr
    influence_by_district: dict[NonEmptyStr, float] = Field(default_factory=dict)
    attitude_toward_player: NonEmptyStr

    @model_validator(mode="after")
    def validate_influence_by_district(self) -> Faction:
        for district_id, influence in self.influence_by_district.items():
            if not 0.0 <= influence <= 1.0:
                raise ValueError(
                    f"influence_by_district values must be between 0.0 and 1.0: {district_id}"
                )

        return self


class FactionConfiguration(SeedModel):
    faction_count: int = Field(ge=0)
    factions: list[Faction]
    tension_map: dict[NonEmptyStr, float] = Field(default_factory=dict)

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

        normalized_tension_map: dict[str, float] = {}
        for raw_key, tension in self.tension_map.items():
            left, separator, right = raw_key.partition("|")
            normalized_key = f"{left.strip()}|{right.strip()}" if separator else raw_key
            if normalized_key in normalized_tension_map:
                raise ValueError(f"tension_map contains duplicate faction pairs after normalization: {normalized_key}")
            normalized_tension_map[normalized_key] = tension
        self.tension_map = normalized_tension_map

        faction_id_set = set(faction_ids)
        for key, tension in self.tension_map.items():
            if not 0.0 <= tension <= 1.0:
                raise ValueError(f"tension_map values must be between 0.0 and 1.0: {key}")

            left, separator, right = key.partition("|")
            if not separator or not left or not right:
                raise ValueError("tension_map keys must use faction_a|faction_b format")
            if left == right:
                raise ValueError("tension_map keys must reference two different factions")
            if left not in faction_id_set or right not in faction_id_set:
                raise ValueError(f"tension_map references unknown faction ids: {key}")

        return self


class LanternConfiguration(SeedModel):
    lantern_system_style: NonEmptyStr
    lantern_ownership_structure: NonEmptyStr
    lantern_maintenance_structure: NonEmptyStr
    lantern_condition_distribution: dict[LanternStateValue, float]
    lantern_reach_profile: NonEmptyStr
    lantern_social_effect_profile: NonEmptyStrList = Field(default_factory=list)
    lantern_memory_effect_profile: NonEmptyStrList = Field(default_factory=list)
    lantern_tampering_probability: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_lantern_configuration(self) -> LanternConfiguration:
        distribution_keys = set(self.lantern_condition_distribution)
        if distribution_keys != ALL_LANTERN_STATES:
            missing_states = ", ".join(sorted(ALL_LANTERN_STATES - distribution_keys))
            extra_states = ", ".join(sorted(distribution_keys - ALL_LANTERN_STATES))
            details: list[str] = []
            if missing_states:
                details.append(f"missing states: {missing_states}")
            if extra_states:
                details.append(f"unexpected states: {extra_states}")
            raise ValueError(
                "lantern_condition_distribution must define every lantern state explicitly"
                + (f" ({'; '.join(details)})" if details else "")
            )

        for state, value in self.lantern_condition_distribution.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"lantern_condition_distribution values must be between 0.0 and 1.0: {state}"
                )

        total = sum(self.lantern_condition_distribution.values())
        if not isclose(total, 1.0, abs_tol=0.01):
            raise ValueError(
                "lantern_condition_distribution must sum approximately to 1.0"
            )
        return self


class MissingnessConfiguration(SeedModel):
    missingness_pressure: float = Field(ge=0.0, le=1.0)
    missingness_scope: NonEmptyStr
    missingness_visibility: NonEmptyStr
    missingness_style: NonEmptyStr
    missingness_targets: NonEmptyStrList = Field(default_factory=list)
    missingness_risk_level: RiskLevel


class CaseSeed(SeedModel):
    id: NonEmptyStr
    type: NonEmptyStr
    intensity: NonEmptyStr
    scope: NonEmptyStr
    involved_district_ids: NonEmptyStrList = Field(default_factory=list)
    involved_faction_ids: NonEmptyStrList = Field(default_factory=list)
    key_npc_ids: NonEmptyStrList = Field(default_factory=list)
    failure_modes: NonEmptyStrList = Field(default_factory=list)


class CaseConfiguration(SeedModel):
    starting_case_count: int = Field(ge=0)
    cases: list[CaseSeed]

    @model_validator(mode="after")
    def validate_cases(self) -> CaseConfiguration:
        if self.starting_case_count != len(self.cases):
            raise ValueError("starting_case_count must match the number of cases")
        return self


class NPCSeed(SeedModel):
    id: NonEmptyStr
    name: NonEmptyStr
    role_category: NonEmptyStr
    district_id: NonEmptyStr
    location_id: NonEmptyStr
    memory_depth: NonEmptyStr
    relationship_density: NonEmptyStr
    secrecy_level: NonEmptyStr
    mobility_pattern: NonEmptyStr
    relevance_level: NonEmptyStr


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
    story_density: NonEmptyStr
    mystery_complexity: NonEmptyStr
    social_resistance: NonEmptyStr
    investigation_pace: NonEmptyStr
    consequence_severity: NonEmptyStr
    revelation_delay: NonEmptyStr
    narrative_strangeness: NonEmptyStr


class CitySeedDocument(SeedModel):
    schema_version: NonEmptyStr
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

        for npc in self.npc_configuration.npcs:
            if npc.district_id not in district_ids:
                raise ValueError(f"npc references unknown district id: {npc.district_id}")

        return self


def validate_city_seed(payload: Any) -> CitySeedDocument:
    return CitySeedDocument.model_validate(payload)


__all__ = ["CitySeedDocument", "validate_city_seed", "ValidationError"]
