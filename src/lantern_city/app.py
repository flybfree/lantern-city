from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path

from lantern_city.bootstrap import bootstrap_city
from lantern_city.cases import transition_case
from lantern_city.clues import clarify_clue
from lantern_city.engine import handle_player_request
from lantern_city.lanterns import LanternRuleProfile, apply_lantern_to_clue
from lantern_city.models import (
    ClueState,
    DistrictState,
    LocationState,
    NPCState,
    PlayerProgressState,
    PlayerRequest,
)
from lantern_city.progression import apply_progress_change
from lantern_city.seed_schema import validate_city_seed
from lantern_city.store import SQLiteStore

TURN_ZERO = "turn_0"
TURN_ONE = "turn_1"
TURN_TWO = "turn_2"
TURN_THREE = "turn_3"
TURN_FOUR = "turn_4"


@dataclass(slots=True)
class LanternCityApp:
    database_path: str | Path
    store: SQLiteStore = field(init=False)

    def __post_init__(self) -> None:
        self.store = SQLiteStore(self.database_path)

    def start_new_game(self) -> str:
        existing_city = self._city()
        if existing_city is not None:
            case = self._active_case(existing_city)
            case_title = "None" if case is None else self._display_case_title(case.title)
            return (
                f"Existing game loaded: {existing_city.id}\n"
                f"Districts: {', '.join(existing_city.district_ids)}\n"
                f"Active case: {case_title}"
            )

        seed = validate_city_seed(_default_seed_payload())
        result = bootstrap_city(seed, self.store)
        self._seed_authored_scene_objects()
        city = self._require_city()
        case = self._active_case(city)
        case_title = "None" if case is None else self._display_case_title(case.title)
        return (
            f"Lantern City ready: seeded {result.city_id}\n"
            f"Districts: {', '.join(result.district_ids)}\n"
            f"Active case: {case_title}\n"
            f"Next: enter district_old_quarter"
        )

    def run_command(self, command: str) -> str:
        parts = shlex.split(command)
        if not parts:
            raise ValueError("Command cannot be empty")

        verb = parts[0].lower()
        if verb == "start":
            return self.start_new_game()
        if verb == "enter" and len(parts) >= 2:
            return self.enter_district(parts[1])
        if verb == "talk" and len(parts) >= 3:
            return self.talk_to_npc(parts[1], " ".join(parts[2:]))
        if verb == "inspect" and len(parts) >= 2:
            return self.inspect_location(parts[1])
        if verb == "case" and len(parts) >= 2:
            return self.advance_case(parts[1])
        raise ValueError(f"Unsupported command: {command}")

    def enter_district(self, district_id: str) -> str:
        city = self._require_city()
        outcome = handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request("district entry", target_id=district_id, updated_at=TURN_ONE),
        )
        district = outcome.active_slice.district
        if district is None:
            raise LookupError(f"District not found: {district_id}")
        visible_npc = "None"
        preferred_npc = next(
            (npc for npc in outcome.active_slice.npcs if npc.id == "npc_shrine_keeper"),
            None,
        )
        if preferred_npc is not None:
            visible_npc = preferred_npc.name
        elif outcome.active_slice.npcs:
            visible_npc = outcome.active_slice.npcs[0].name
        return (
            f"District: {district.name}\n"
            f"Lanterns: {district.lantern_condition}\n"
            f"Notable NPC: {visible_npc}\n"
            f"Summary: {outcome.response.narrative_text}"
        )

    def talk_to_npc(self, npc_id: str, prompt: str) -> str:
        city = self._require_city()
        outcome = handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request(
                "talk to NPC",
                target_id=npc_id,
                input_text=prompt,
                updated_at=TURN_TWO,
            ),
        )
        npc = outcome.active_slice.npcs[0]
        clue = self._primary_clue()
        progress = self._require_progress()
        updates = []

        if clue is not None and clue.reliability != "solid":
            clue = clarify_clue(
                clue,
                clarification_text=f"{npc.name} ties the ledger marks to the missing clerk.",
                updated_at=TURN_TWO,
            )
            updates.append(clue)

        progress, _ = apply_progress_change(
            progress,
            track="clue_mastery",
            amount=4,
            reason="Connected witness testimony to the first ledger clue.",
            updated_at=TURN_TWO,
        )
        updates.append(progress)
        self.store.save_objects_atomically(updates)

        clue_text = "None"
        clue_reliability = "unknown"
        if clue is not None:
            clue_text = clue.id
            clue_reliability = clue.reliability
        return (
            f"{outcome.response.narrative_text}\n"
            f"Clue: {clue_text}\n"
            f"Reliability: {clue_reliability}"
        )

    def inspect_location(self, location_id: str) -> str:
        city = self._require_city()
        outcome = handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request("inspect location", target_id=location_id, updated_at=TURN_THREE),
        )
        district = outcome.active_slice.district
        clue = self._primary_clue()
        if district is None or clue is None:
            return outcome.response.text

        lantern_profile = LanternRuleProfile(
            state=district.lantern_condition,
            missingness=_missingness_level(city.missingness_pressure),
        )
        updated_clue = apply_lantern_to_clue(clue, lantern_profile, updated_at=TURN_THREE)
        progress = self._require_progress()
        progress, _ = apply_progress_change(
            progress,
            track="lantern_understanding",
            amount=3,
            reason="Checked the clue against local lantern conditions.",
            updated_at=TURN_THREE,
        )
        self.store.save_objects_atomically([updated_clue, progress])
        return (
            f"Lantern check: {district.lantern_condition}\n"
            f"Location: {location_id}\n"
            f"Clue reliability: {updated_clue.reliability}"
        )

    def advance_case(self, case_id: str) -> str:
        city = self._require_city()
        handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request("review case", target_id=case_id, updated_at=TURN_FOUR),
        )
        case = self._active_case(city)
        clue = self._primary_clue()
        npc = self._npc("npc_shrine_keeper")
        progress = self._require_progress()
        if case is None or clue is None or npc is None:
            raise LookupError("Missing state required for case progression")

        solved = clue.reliability in {"credible", "solid"} and bool(npc.memory_log)
        new_status = "solved" if solved else "escalated"
        updated_case = transition_case(
            case,
            new_status,
            updated_at=TURN_FOUR,
            resolution_summary=(
                "The first lead is strong enough to pin the clerk's trail to the altered ledgers."
                if solved
                else None
            ),
            fallout_summary="The Old Quarter starts reacting to the clerk case.",
        )
        self.store.save_object(updated_case)
        progress = self._require_progress()
        return (
            f"Case status: {updated_case.status}\n"
            f"Case: {updated_case.title}\n"
            "Lantern understanding: "
            f"{progress.lantern_understanding.score} "
            f"({progress.lantern_understanding.tier})"
        )

    def get_state_snapshot(self) -> dict[str, object]:
        city = self._require_city()
        case = self._active_case(city)
        clue = self._primary_clue()
        npc = self._npc("npc_shrine_keeper")
        progress = self._require_progress()
        lantern_condition = "unknown"
        if case is not None and case.involved_district_ids:
            district = self._district(case.involved_district_ids[0])
            if district is not None:
                lantern_condition = district.lantern_condition
        return {
            "city_id": city.id,
            "case_status": None if case is None else case.status,
            "clue_reliability": None if clue is None else clue.reliability,
            "lantern_condition": lantern_condition,
            "npc_memory_count": 0 if npc is None else len(npc.memory_log),
            "lantern_understanding_score": progress.lantern_understanding.score,
        }

    def _seed_authored_scene_objects(self) -> None:
        old_quarter = self._district("district_old_quarter")
        lantern_ward = self._district("district_lantern_ward")
        shrine_keeper = self._npc("npc_shrine_keeper")
        archive_clerk = self._npc("npc_archive_clerk")
        if (
            old_quarter is None
            or lantern_ward is None
            or shrine_keeper is None
            or archive_clerk is None
        ):
            raise LookupError("Bootstrap did not create required authored objects")

        shrine_lane = LocationState(
            id="location_shrine_lane",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Shrine Lane",
            location_type="shrine",
            known_npc_ids=[shrine_keeper.id],
            clue_ids=["clue_missing_clerk_ledgers"],
        )
        archive_steps = LocationState(
            id="location_archive_steps",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Archive Steps",
            location_type="archive",
            known_npc_ids=[archive_clerk.id],
        )
        lantern_square = LocationState(
            id="location_lantern_square",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=lantern_ward.id,
            name="Lantern Square",
            location_type="civic",
        )
        clue = ClueState(
            id="clue_missing_clerk_ledgers",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="document",
            source_id=shrine_lane.id,
            clue_text=(
                "Ledger initials near the missing clerk's route do not match the public "
                "register."
            ),
            reliability="credible",
            related_npc_ids=[shrine_keeper.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        updated_old_quarter = old_quarter.model_copy(
            update={
                "visible_locations": [shrine_lane.id, archive_steps.id],
                "version": old_quarter.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_lantern_ward = lantern_ward.model_copy(
            update={
                "visible_locations": [lantern_square.id],
                "version": lantern_ward.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_shrine_keeper = shrine_keeper.model_copy(
            update={
                "known_clue_ids": [clue.id],
                "public_identity": "shrine keeper",
                "version": shrine_keeper.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        self.store.save_objects_atomically(
            [
                updated_old_quarter,
                updated_lantern_ward,
                updated_shrine_keeper,
                shrine_lane,
                archive_steps,
                lantern_square,
                clue,
            ]
        )

    def _request(
        self,
        intent: str,
        *,
        target_id: str | None = None,
        input_text: str = "",
        updated_at: str,
    ) -> PlayerRequest:
        request_id = f"request_{intent.replace(' ', '_')}_{target_id or 'none'}"
        return PlayerRequest(
            id=request_id,
            created_at=updated_at,
            updated_at=updated_at,
            player_id="player_001",
            intent=intent,
            target_id=target_id,
            input_text=input_text,
        )

    def _city(self):
        cities = self.store.list_objects("CityState")
        return None if not cities else cities[0]

    def _require_city(self):
        city = self._city()
        if city is None:
            raise LookupError("No active game. Run start first.")
        return city

    def _district(self, district_id: str) -> DistrictState | None:
        district = self.store.load_object("DistrictState", district_id)
        return district if isinstance(district, DistrictState) else None

    def _npc(self, npc_id: str) -> NPCState | None:
        npc = self.store.load_object("NPCState", npc_id)
        return npc if isinstance(npc, NPCState) else None

    def _active_case(self, city) -> object:
        if not city.active_case_ids:
            return None
        return self.store.load_object("CaseState", city.active_case_ids[0])

    def _primary_clue(self) -> ClueState | None:
        clue = self.store.load_object("ClueState", "clue_missing_clerk_ledgers")
        return clue if isinstance(clue, ClueState) else None

    def _require_progress(self) -> PlayerProgressState:
        progress_items = self.store.list_objects("PlayerProgressState")
        if not progress_items:
            raise LookupError("No player progress found")
        progress = progress_items[0]
        if not isinstance(progress, PlayerProgressState):
            raise TypeError("Stored progress is not a PlayerProgressState")
        return progress

    def _display_case_title(self, title: str) -> str:
        return title if title.lower().startswith("the ") else f"The {title}"


def _missingness_level(pressure: float) -> str:
    if pressure >= 0.67:
        return "high"
    if pressure >= 0.33:
        return "medium"
    if pressure > 0:
        return "low"
    return "none"


def _default_seed_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "city_identity": {
            "city_name": "Lantern City",
            "dominant_mood": ["noir", "wet", "uncertain"],
            "weather_pattern": ["persistent rain", "coastal fog"],
            "architectural_style": ["old stone", "brass fixtures"],
            "economic_character": ["port trade", "recordkeeping"],
            "social_texture": ["guarded", "rumor-driven"],
            "ritual_texture": ["formal lantern ceremonies", "hidden shrine practice"],
            "baseline_noise_level": "medium",
        },
        "district_configuration": {
            "district_count": 2,
            "districts": [
                {
                    "id": "district_old_quarter",
                    "name": "Old Quarter",
                    "role": "memory/archive district",
                    "stability_baseline": 0.47,
                    "lantern_state": "dim",
                    "access_pattern": "restricted",
                    "hidden_location_density": "medium",
                },
                {
                    "id": "district_lantern_ward",
                    "name": "Lantern Ward",
                    "role": "administrative lantern district",
                    "stability_baseline": 0.71,
                    "lantern_state": "bright",
                    "access_pattern": "controlled",
                    "hidden_location_density": "low",
                },
            ],
        },
        "faction_configuration": {
            "faction_count": 2,
            "factions": [
                {
                    "id": "faction_memory_keepers",
                    "name": "Memory Keepers",
                    "role": "memory stewardship",
                    "public_goal": "preserve continuity",
                    "hidden_goal": "control what the city remembers",
                    "influence_by_district": {
                        "district_old_quarter": 0.78,
                        "district_lantern_ward": 0.22,
                    },
                    "attitude_toward_player": "wary",
                },
                {
                    "id": "faction_council_lights",
                    "name": "Council of Lights",
                    "role": "civic lantern administration",
                    "public_goal": "maintain public order",
                    "hidden_goal": "monopolize lantern legitimacy",
                    "influence_by_district": {
                        "district_old_quarter": 0.18,
                        "district_lantern_ward": 0.81,
                    },
                    "attitude_toward_player": "guarded",
                },
            ],
            "tension_map": {"faction_memory_keepers|faction_council_lights": 0.58},
        },
        "lantern_configuration": {
            "lantern_system_style": "civic grid with ritual overlays",
            "lantern_ownership_structure": "mixed control",
            "lantern_maintenance_structure": "shrine technicians and civic engineers",
            "lantern_condition_distribution": {
                "bright": 0.4,
                "dim": 0.35,
                "flickering": 0.15,
                "extinguished": 0.05,
                "altered": 0.05,
            },
            "lantern_reach_profile": "district-wide with street-level exceptions",
            "lantern_social_effect_profile": ["legitimacy", "restricted movement"],
            "lantern_memory_effect_profile": ["clearer testimony", "contradictory accounts"],
            "lantern_tampering_probability": 0.22,
        },
        "missingness_configuration": {
            "missingness_pressure": 0.42,
            "missingness_scope": "records first",
            "missingness_visibility": "known-but-denied",
            "missingness_style": "edited records and contradictory witness accounts",
            "missingness_targets": ["families", "archives"],
            "missingness_risk_level": "medium",
        },
        "case_configuration": {
            "starting_case_count": 1,
            "cases": [
                {
                    "id": "case_missing_clerk",
                    "type": "missing person",
                    "intensity": "medium",
                    "scope": "single district",
                    "involved_district_ids": ["district_old_quarter"],
                    "involved_faction_ids": ["faction_memory_keepers"],
                    "key_npc_ids": ["npc_shrine_keeper", "npc_archive_clerk"],
                    "failure_modes": ["evidence destroyed", "Missingness escalates"],
                }
            ],
        },
        "npc_configuration": {
            "tracked_npc_count": 2,
            "npcs": [
                {
                    "id": "npc_shrine_keeper",
                    "name": "Ila Venn",
                    "role_category": "informant",
                    "district_id": "district_old_quarter",
                    "location_id": "location_shrine_lane",
                    "memory_depth": "medium",
                    "relationship_density": "medium",
                    "secrecy_level": "high",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "immediate",
                },
                {
                    "id": "npc_archive_clerk",
                    "name": "Sered Marr",
                    "role_category": "witness",
                    "district_id": "district_old_quarter",
                    "location_id": "location_archive_steps",
                    "memory_depth": "high",
                    "relationship_density": "medium",
                    "secrecy_level": "medium",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "immediate",
                },
            ],
        },
        "progression_start_state": {
            "starting_lantern_understanding": 18,
            "starting_access": 10,
            "starting_reputation": 12,
            "starting_leverage": 5,
            "starting_city_impact": 2,
            "starting_clue_mastery": 20,
        },
        "tone_and_difficulty": {
            "story_density": "medium",
            "mystery_complexity": "medium",
            "social_resistance": "medium",
            "investigation_pace": "moderate",
            "consequence_severity": "medium",
            "revelation_delay": "medium",
            "narrative_strangeness": "medium",
        },
    }


__all__ = ["LanternCityApp"]
