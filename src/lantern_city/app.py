from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path

from lantern_city.bootstrap import bootstrap_city
from lantern_city.cases import transition_case
from lantern_city.clues import clarify_clue
from lantern_city.engine import handle_player_request
from lantern_city.lanterns import LanternRuleProfile, apply_lantern_to_clue, is_corroborated
from lantern_city.llm_client import OpenAICompatibleConfig
from lantern_city.models import (
    ClueState,
    DistrictState,
    LocationState,
    NPCState,
    PlayerProgressState,
    PlayerRequest,
)
from lantern_city.progression import apply_progress_change, get_tier
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
    llm_config: OpenAICompatibleConfig | None = None
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
            llm_config=self.llm_config,
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
        available_npcs = (
            ", ".join(f"{npc.id} ({npc.name})" for npc in outcome.active_slice.npcs)
            if outcome.active_slice.npcs
            else "None"
        )
        available_locations = (
            ", ".join(outcome.active_slice.district.visible_locations)
            if outcome.active_slice.district is not None and outcome.active_slice.district.visible_locations
            else "None"
        )
        return (
            f"District: {district.name}\n"
            f"Lanterns: {district.lantern_condition}\n"
            f"Notable NPC: {visible_npc}\n"
            f"Available NPC IDs: {available_npcs}\n"
            f"Available location IDs: {available_locations}\n"
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
            llm_config=self.llm_config,
        )
        npc = outcome.active_slice.npcs[0]
        clue = self._npc_clue(npc)
        progress = self._require_progress()
        updates = []

        if clue is not None and clue.reliability != "solid":
            clue = clarify_clue(
                clue,
                clarification_text=f"{npc.name} provides testimony connecting the evidence to the case.",
                updated_at=TURN_TWO,
            )
            updates.append(clue)

        progress, _ = apply_progress_change(
            progress,
            track="clue_mastery",
            amount=4,
            reason=f"Gained testimony from {npc.name}.",
            updated_at=TURN_TWO,
        )
        updates.append(progress)
        self.store.save_objects_atomically(updates)

        district = outcome.active_slice.district
        propagation_notices = []
        if district is not None:
            city = self._require_city()
            propagation_notices = self._propagate_missingness(city, district, updated_at=TURN_TWO)

        clue_text = "None"
        clue_reliability = "unknown"
        if clue is not None:
            clue_text = clue.id
            clue_reliability = clue.reliability
        lines = [f"{outcome.response.narrative_text}", f"Clue: {clue_text}", f"Reliability: {clue_reliability}"]
        lines.extend(propagation_notices)
        return "\n".join(lines)

    def inspect_location(self, location_id: str, object_name: str | None = None) -> str:
        city = self._require_city()
        outcome = handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request(
                "inspect location",
                target_id=location_id,
                input_text=object_name or "",
                updated_at=TURN_THREE,
            ),
            llm_config=self.llm_config,
        )
        district = outcome.active_slice.district
        if district is None:
            return outcome.response.narrative_text

        lantern_profile = LanternRuleProfile(
            state=district.lantern_condition,
            missingness=_missingness_level(city.missingness_pressure),
        )
        all_clues = outcome.active_slice.clues
        inspected_location_id = location_id
        updated_clues = [
            _apply_physical_discovery(
                apply_lantern_to_clue(
                    clue,
                    lantern_profile,
                    updated_at=TURN_THREE,
                    corroborated=is_corroborated(clue, all_clues),
                ),
                location_id=inspected_location_id,
                updated_at=TURN_THREE,
            )
            for clue in all_clues
        ]
        progress = self._require_progress()
        progress, _ = apply_progress_change(
            progress,
            track="lantern_understanding",
            amount=3,
            reason="Checked clues against local lantern conditions.",
            updated_at=TURN_THREE,
        )
        self.store.save_objects_atomically([*updated_clues, progress])

        propagation_notices = self._propagate_missingness(city, district, updated_at=TURN_THREE)

        lines = []
        if object_name:
            lines.append(f"Examining: {object_name}")
        lines.append(outcome.response.narrative_text)
        if outcome.response.learned:
            lines.append("Observed:")
            for detail in outcome.response.learned:
                lines.append(f"  - {detail}")
        location = outcome.active_slice.location
        if not object_name and location is not None and location.scene_objects:
            lines.append("Objects here:")
            for obj in location.scene_objects:
                lines.append(f"  - {obj}")
        clue_status = " | ".join(
            f"{_clue_label(c.id)}: {c.reliability}" for c in updated_clues
        )
        lines.append(f"[Lantern: {district.lantern_condition} | {clue_status}]")
        lines.extend(propagation_notices)
        return "\n".join(lines)

    def advance_case(self, case_id: str) -> str:
        city = self._require_city()
        handle_player_request(
            self.store,
            city_id=city.id,
            request=self._request("review case", target_id=case_id, updated_at=TURN_FOUR),
            llm_config=self.llm_config,
        )
        case = self._active_case(city)
        progress = self._require_progress()
        if case is None:
            raise LookupError("No active case found")

        path, new_status, resolution_summary, fallout_summary = _assess_resolution(
            self.store, progress
        )

        updated_case = transition_case(
            case,
            new_status,
            updated_at=TURN_FOUR,
            resolution_summary=resolution_summary,
            fallout_summary=fallout_summary,
        )
        self.store.save_object(updated_case)

        progress = self._require_progress()
        for track, amount, reason in _RESOLUTION_GAINS[path]:
            progress, _ = apply_progress_change(
                progress,
                track=track,
                amount=amount,
                reason=reason,
                updated_at=TURN_FOUR,
            )
        self.store.save_object(progress)

        lines = [
            f"Case status: {updated_case.status}",
            f"Resolution: {path.replace('_', ' ')}",
            f"Case: {updated_case.title}",
            f"Lantern understanding: {progress.lantern_understanding.score} ({progress.lantern_understanding.tier})",
            f"Access: {progress.access.score} ({progress.access.tier})",
            f"Leverage: {progress.leverage.score} ({progress.leverage.tier})",
        ]
        return "\n".join(lines)

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

    def _propagate_missingness(
        self,
        city: object,
        district: DistrictState,
        *,
        updated_at: str,
    ) -> list[str]:
        """Degrade vulnerable clues when missingness conditions are met.

        Fires when: pressure is medium/high + lantern is strained + unresolved contradiction exists.
        Physical clues are immune. Testimony degrades first; documents follow at high pressure.
        Returns player-facing notices for any clues that worsened.
        """
        pressure_level = _missingness_level(getattr(city, "missingness_pressure", 0.0))
        if pressure_level not in {"medium", "high"}:
            return []
        if district.lantern_condition not in {"dim", "flickering", "extinguished", "altered"}:
            return []

        clues = [
            obj
            for clue_id in _CASE_CLUE_IDS
            if isinstance(obj := self.store.load_object("ClueState", clue_id), ClueState)
        ]

        # Propagation only fires when an unresolved contradiction exists in the case
        if not any(c.reliability == "contradicted" for c in clues):
            return []

        degraded: list[ClueState] = []
        notices: list[str] = []

        for clue in clues:
            if clue.reliability not in {"uncertain", "unstable"}:
                continue
            if clue.source_type == "physical":
                continue  # Physical evidence resists propagation

            # Testimony degrades under medium+ pressure; documents only under high
            should_degrade = (
                pressure_level == "high"
                or (pressure_level == "medium" and clue.source_type == "testimony")
            )

            if should_degrade and clue.reliability == "uncertain":
                degraded.append(
                    clue.model_copy(update={"reliability": "unstable", "updated_at": updated_at})
                )
                notices.append(
                    f"[Pressure: {_clue_label(clue.id)} is drifting - reliability now unstable]"
                )

        if degraded:
            self.store.save_objects_atomically(degraded)

        # Under severe conditions (flickering+), increase city pressure slightly
        if district.lantern_condition in {"flickering", "extinguished"} and pressure_level == "medium":
            new_pressure = min(1.0, getattr(city, "missingness_pressure", 0.0) + 0.05)
            updated_city = city.model_copy(  # type: ignore[union-attr]
                update={"missingness_pressure": new_pressure, "updated_at": updated_at}
            )
            self.store.save_object(updated_city)

        return notices

    def _seed_authored_scene_objects(self) -> None:
        old_quarter = self._district("district_old_quarter")
        lantern_ward = self._district("district_lantern_ward")
        shrine_keeper = self._npc("npc_shrine_keeper")
        archive_clerk = self._npc("npc_archive_clerk")
        brin_hesse = self._npc("npc_brin_hesse")
        tovin_vale = self._npc("npc_tovin_vale")
        if (
            old_quarter is None
            or lantern_ward is None
            or shrine_keeper is None
            or archive_clerk is None
            or brin_hesse is None
            or tovin_vale is None
        ):
            raise LookupError("Bootstrap did not create required authored objects")

        # --- Locations ---
        shrine_lane = LocationState(
            id="location_shrine_lane",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Shrine Lane",
            location_type="shrine",
            known_npc_ids=[shrine_keeper.id],
            clue_ids=["clue_missing_clerk_ledgers", "clue_outage_predates_disappearance", "clue_heat_scoring_on_bracket"],
            scene_objects=["lantern bracket", "offering ledger", "shrine workroom door"],
        )
        archive_steps = LocationState(
            id="location_archive_steps",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Archive Steps",
            location_type="archive",
            known_npc_ids=[archive_clerk.id],
            clue_ids=["clue_family_record_discrepancy"],
            scene_objects=["registry board", "ledger shelf", "archive entrance log"],
        )
        ledger_room = LocationState(
            id="location_ledger_room",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Ledger Room",
            location_type="records",
            known_npc_ids=[archive_clerk.id],
            clue_ids=["clue_missing_maintenance_line"],
            scene_objects=["maintenance log shelf", "sealed inkwell", "service ledger"],
        )
        maintenance_route = LocationState(
            id="location_maintenance_route",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Maintenance Route",
            location_type="service passage",
            known_npc_ids=[brin_hesse.id],
            scene_objects=["soot-marked archway", "lantern mounting", "service key rack"],
        )
        service_passage = LocationState(
            id="location_service_passage",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Service Passage",
            location_type="service passage",
            known_npc_ids=[brin_hesse.id],
            clue_ids=["clue_hidden_copy_sheet"],
            scene_objects=["service latch", "unauthorized tool marks", "narrow passage deeper"],
        )
        subarchive_chamber = LocationState(
            id="location_subarchive_chamber",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=old_quarter.id,
            name="Subarchive Chamber",
            location_type="hidden chamber",
            known_npc_ids=[tovin_vale.id],
            scene_objects=["collapsed shelving", "copied registry fragments", "broken lantern housing"],
        )
        lantern_square = LocationState(
            id="location_lantern_square",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=lantern_ward.id,
            name="Lantern Square",
            location_type="civic",
            scene_objects=["public lantern post", "civic notice board"],
        )

        # --- Clues ---
        clue_a = ClueState(
            id="clue_missing_clerk_ledgers",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="document",
            source_id=shrine_lane.id,
            clue_text=(
                "Ledger initials near the missing clerk's route do not match the public register."
            ),
            reliability="credible",
            related_npc_ids=[shrine_keeper.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_c = ClueState(
            id="clue_heat_scoring_on_bracket",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="physical",
            source_id=shrine_lane.id,
            clue_text=(
                "The lantern bracket at Shrine Lane shows heat scoring inconsistent "
                "with routine wear — the damage pattern indicates deliberate adjustment, "
                "not neglect or failure."
            ),
            reliability="credible",
            related_npc_ids=[shrine_keeper.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_b = ClueState(
            id="clue_outage_predates_disappearance",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="testimony",
            source_id=shrine_lane.id,
            clue_text=(
                "The lantern near the archive was failing before Tovin Vale "
                "was officially reported missing."
            ),
            reliability="uncertain",
            related_npc_ids=[shrine_keeper.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_e = ClueState(
            id="clue_family_record_discrepancy",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="document",
            source_id=archive_steps.id,
            clue_text=(
                "A family entry in the civic register has been edited in the same "
                "archival section where Tovin Vale's name is inconsistent — "
                "suggesting the altered lantern field was used to distort more than one record."
            ),
            reliability="contradicted",
            related_npc_ids=[archive_clerk.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_g = ClueState(
            id="clue_witness_instability",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="composite",
            source_id=old_quarter.id,
            clue_text=(
                "Accounts of Tovin Vale's last movements conflict specifically among "
                "witnesses who were near the affected lantern — those further away "
                "agree, suggesting the inconsistency is spatially bounded, not social rumor."
            ),
            reliability="uncertain",
            related_npc_ids=[shrine_keeper.id, archive_clerk.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_d = ClueState(
            id="clue_missing_maintenance_line",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="document",
            source_id=ledger_room.id,
            clue_text=(
                "A maintenance visit to the archive lantern has been removed "
                "or rewritten in the official service record."
            ),
            reliability="uncertain",
            related_npc_ids=[brin_hesse.id, archive_clerk.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )
        clue_f = ClueState(
            id="clue_hidden_copy_sheet",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            source_type="physical",
            source_id=service_passage.id,
            clue_text=(
                "A handwritten copy of the altered registry entry, hidden behind the service latch. "
                "The hand matches Tovin Vale's known script — he knew the edit was deliberate "
                "and tried to preserve the original before disappearing."
            ),
            reliability="uncertain",
            related_npc_ids=[tovin_vale.id],
            related_case_ids=["case_missing_clerk"],
            related_district_ids=[old_quarter.id],
        )

        # --- District updates ---
        updated_old_quarter = old_quarter.model_copy(
            update={
                "visible_locations": [
                    shrine_lane.id,
                    archive_steps.id,
                    ledger_room.id,
                    maintenance_route.id,
                    service_passage.id,
                ],
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

        # --- NPC updates with cast-sheet values ---
        updated_shrine_keeper = shrine_keeper.model_copy(
            update={
                "public_identity": "shrine keeper",
                "hidden_objective": (
                    "Avoid exposing how much she knows about the lantern alteration. "
                    "Prevent blame from falling entirely on the shrine."
                ),
                "current_objective": (
                    "Keep the local lantern from destabilizing further. "
                    "See the truth handled by someone more capable than the archive office."
                ),
                "trust_in_player": 0.25,
                "suspicion": 0.4,
                "fear": 0.4,
                "known_clue_ids": [clue_a.id, clue_b.id, clue_c.id, clue_g.id],
                "version": shrine_keeper.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_archive_clerk = archive_clerk.model_copy(
            update={
                "public_identity": "acting archive registrar",
                "hidden_objective": (
                    "Keep the incident from becoming a scandal. "
                    "Avoid superiors discovering how compromised local records became."
                ),
                "current_objective": (
                    "Preserve archive credibility. Contain the records discrepancy."
                ),
                "trust_in_player": 0.1,
                "suspicion": 0.55,
                "fear": 0.4,
                "known_clue_ids": [clue_d.id, clue_e.id],
                "version": archive_clerk.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_brin_hesse = brin_hesse.model_copy(
            update={
                "public_identity": "lamplighter's assistant",
                "hidden_objective": (
                    "Cover for a paid errand that moved a maintenance key at the wrong time."
                ),
                "current_objective": (
                    "Avoid punishment from both the council and local maintenance crews."
                ),
                "trust_in_player": 0.3,
                "suspicion": 0.7,
                "fear": 0.8,
                "known_clue_ids": [clue_d.id],
                "version": brin_hesse.version + 1,
                "updated_at": TURN_ZERO,
            }
        )
        updated_tovin_vale = tovin_vale.model_copy(
            update={
                "public_identity": "registry clerk, officially missing",
                "hidden_objective": (
                    "Survive. Be found by someone who will act on what they find, "
                    "not suppress it further."
                ),
                "current_objective": (
                    "Wait. The copy sheet is hidden. If someone reaches the passage, "
                    "they can find it. If they reach this chamber, they can hear the full account."
                ),
                "trust_in_player": 0.0,
                "suspicion": 0.85,
                "fear": 0.95,
                "known_clue_ids": [clue_f.id],
                "version": tovin_vale.version + 1,
                "updated_at": TURN_ZERO,
            }
        )

        self.store.save_objects_atomically(
            [
                updated_old_quarter,
                updated_lantern_ward,
                updated_shrine_keeper,
                updated_archive_clerk,
                updated_brin_hesse,
                updated_tovin_vale,
                shrine_lane,
                archive_steps,
                ledger_room,
                maintenance_route,
                service_passage,
                subarchive_chamber,
                lantern_square,
                clue_a,
                clue_b,
                clue_c,
                clue_d,
                clue_e,
                clue_f,
                clue_g,
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

    def _npc_clue(self, npc: NPCState) -> ClueState | None:
        """Return the first non-solid clue from this NPC's known_clue_ids, or the primary clue."""
        for clue_id in npc.known_clue_ids:
            clue = self.store.load_object("ClueState", clue_id)
            if isinstance(clue, ClueState) and clue.reliability != "solid":
                return clue
        return self._primary_clue()

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


def _clue_label(clue_id: str) -> str:
    if clue_id.startswith("clue_"):
        return clue_id[5:].replace("_", " ").title()
    return clue_id


def _apply_physical_discovery(
    clue: ClueState,
    *,
    location_id: str,
    updated_at: str,
) -> ClueState:
    """Physical clues found at the inspected location upgrade to at least credible."""
    if clue.source_type != "physical":
        return clue
    if clue.source_id != location_id:
        return clue
    if clue.reliability in _CREDIBLE_RELIABILITIES or clue.reliability == "contradicted":
        return clue
    return clue.model_copy(update={"reliability": "credible", "updated_at": updated_at})


def _missingness_level(pressure: float) -> str:
    if pressure >= 0.67:
        return "high"
    if pressure >= 0.33:
        return "medium"
    if pressure > 0:
        return "low"
    return "none"


_CASE_CLUE_IDS = [
    "clue_missing_clerk_ledgers",
    "clue_heat_scoring_on_bracket",
    "clue_outage_predates_disappearance",
    "clue_missing_maintenance_line",
    "clue_family_record_discrepancy",
    "clue_hidden_copy_sheet",
    "clue_witness_instability",
]
_CREDIBLE_RELIABILITIES = {"credible", "solid"}
# (track, amount, reason)
_RESOLUTION_GAINS: dict[str, list[tuple[str, int, str]]] = {
    "clean_exposure": [
        ("reputation", 10, "Public exposure of lantern manipulation and records fraud."),
        ("city_impact", 12, "Truth entered civic memory; district accountability forced."),
        ("access", 5, "Credibility gained through documented proof."),
        ("clue_mastery", 6, "Evidence chain assembled and presented under pressure."),
    ],
    "quiet_rescue": [
        ("access", 6, "Hidden routes used; Tovin extracted without public exposure."),
        ("reputation", 4, "Trusted by local actors for discretion."),
        ("leverage", 5, "Proof preserved; political use remains possible later."),
        ("clue_mastery", 4, "Case resolved through careful evidence handling."),
    ],
    "political_bargain": [
        ("leverage", 12, "Silence or partial silence traded for access or restoration."),
        ("access", 4, "Institutional doors opened through negotiation."),
        ("clue_mastery", 3, "Contradictions converted into durable leverage."),
    ],
    "partial_failure": [
        ("lantern_understanding", 4, "Lantern distortion identified and partially contained."),
        ("clue_mastery", 4, "Evidence gathered, case mechanism understood."),
    ],
    "burial": [
        ("lantern_understanding", 2, "Partial observation before the case closed against truth."),
    ],
}


def _assess_resolution(
    store: SQLiteStore, progress: PlayerProgressState
) -> tuple[str, str, str, str]:
    """Determine the resolution path, case status, and summary strings."""
    clues = [
        obj
        for clue_id in _CASE_CLUE_IDS
        if isinstance(obj := store.load_object("ClueState", clue_id), ClueState)
    ]
    credible_clues = [c for c in clues if c.reliability in _CREDIBLE_RELIABILITIES]
    clue_f = next((c for c in clues if c.id == "clue_hidden_copy_sheet"), None)
    has_clue_f = clue_f is not None and clue_f.reliability in _CREDIBLE_RELIABILITIES
    access_tier = get_tier(progress.access.score)
    leverage_tier = get_tier(progress.leverage.score)

    if has_clue_f and len(credible_clues) >= 2 and (access_tier >= 2 or leverage_tier >= 2):
        return (
            "clean_exposure",
            "solved",
            (
                "Tovin Vale's hidden copy sheet, combined with physical evidence of deliberate "
                "lantern alteration, was presented to unavoidable authority. The manipulation "
                "entered the record. The district had to respond."
            ),
            (
                "Archive credibility shaken. Shrine Lane tensions surface. "
                "Old Quarter remembers this differently going forward."
            ),
        )

    if has_clue_f and len(credible_clues) >= 1:
        return (
            "quiet_rescue",
            "solved",
            (
                "Tovin Vale was located and extracted through the hidden route. "
                "Enough proof was preserved to prevent his disappearance from becoming permanent, "
                "but the full institutional truth was not forced into the public record."
            ),
            (
                "Tovin survives, off the books. Archive formally stable. "
                "Shrine keeper trust gains. The system that hid him remains."
            ),
        )

    if leverage_tier >= 2 and len(credible_clues) >= 1:
        return (
            "political_bargain",
            "solved",
            (
                "Evidence of the missing maintenance line and record discrepancies was used "
                "as leverage rather than public proof. An arrangement was reached. "
                "The case closes without scandal."
            ),
            (
                "Case closed quietly. One official remains compromised. "
                "Future cases may reference this silence."
            ),
        )

    if len(credible_clues) >= 1:
        return (
            "partial_failure",
            "partially solved",
            (
                "The lantern distortion was identified and partly stabilized, "
                "but the case closed without recovering Tovin Vale or proving full institutional guilt."
            ),
            (
                "District stops worsening. Records can be corrected later. "
                "Tovin's fate remains unresolved."
            ),
        )

    return (
        "burial",
        "failed",
        (
            "The investigation produced insufficient evidence before the case was forced to close. "
            "The official account hardened around the false version."
        ),
        (
            "Official records settle. District superficially calmer. "
            "Truth buried. Missingness pressure increases for future cases."
        ),
    )


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
                    "key_npc_ids": ["npc_shrine_keeper", "npc_archive_clerk", "npc_brin_hesse", "npc_tovin_vale"],
                    "failure_modes": ["evidence destroyed", "Missingness escalates"],
                }
            ],
        },
        "npc_configuration": {
            "tracked_npc_count": 4,
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
                    "role_category": "gatekeeper",
                    "district_id": "district_old_quarter",
                    "location_id": "location_archive_steps",
                    "memory_depth": "high",
                    "relationship_density": "medium",
                    "secrecy_level": "high",
                    "mobility_pattern": "district-bound",
                    "relevance_level": "immediate",
                },
                {
                    "id": "npc_brin_hesse",
                    "name": "Brin Hesse",
                    "role_category": "informant",
                    "district_id": "district_old_quarter",
                    "location_id": "location_maintenance_route",
                    "memory_depth": "low",
                    "relationship_density": "low",
                    "secrecy_level": "medium",
                    "mobility_pattern": "route-bound",
                    "relevance_level": "secondary",
                },
                {
                    "id": "npc_tovin_vale",
                    "name": "Tovin Vale",
                    "role_category": "informant",
                    "district_id": "district_old_quarter",
                    "location_id": "location_subarchive_chamber",
                    "memory_depth": "high",
                    "relationship_density": "low",
                    "secrecy_level": "extreme",
                    "mobility_pattern": "stationary",
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
