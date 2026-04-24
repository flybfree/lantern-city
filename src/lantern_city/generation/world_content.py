"""World content generation for Lantern City.

Given a bootstrapped city (districts, NPCs, cases), generates:
  - Locations for each district (3–5 per district)
  - Clues for each starting case (4–6 clues across relevant locations)
  - NPC placement (each NPC assigned to exactly one location)
  - District visible/hidden location lists
  - NPC location_id and known_clue_ids updates

This replaces hand-authored scene objects when an LLM is available.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from lantern_city.models import (
    CaseState,
    ClueState,
    DistrictState,
    LocationState,
    NPCState,
)

TURN_ZERO = "turn_0"

_VALID_SOURCE_TYPES = frozenset({"document", "physical", "testimony", "composite"})
_VALID_RELIABILITIES = frozenset({"credible", "uncertain", "contradicted", "unstable"})


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


_LOCATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id_slug": {"type": "string", "description": "Unique snake_case suffix, e.g. 'archive_steps'"},
                    "name": {"type": "string"},
                    "location_type": {"type": "string"},
                    "npc_ids": {"type": "array", "items": {"type": "string"}},
                    "scene_objects": {"type": "array", "items": {"type": "string"}},
                    "is_hidden": {"type": "boolean"},
                },
                "required": ["id_slug", "name", "location_type", "npc_ids", "scene_objects", "is_hidden"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["locations"],
    "additionalProperties": False,
}

_CASE_BRIEFING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Evocative case title (max 80 chars)",
        },
        "discovery_hook": {
            "type": "string",
            "description": "2-3 sentences: who brought you this case, what they said, what you know so far",
        },
        "objective_summary": {
            "type": "string",
            "description": "1-2 sentences: what you need to find out or accomplish",
        },
    },
    "required": ["title", "discovery_hook", "objective_summary"],
    "additionalProperties": False,
}

_CLUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "clues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id_slug": {"type": "string", "description": "Unique snake_case suffix, e.g. 'missing_ledger'"},
                    "clue_text": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["document", "physical", "testimony", "composite"]},
                    "reliability": {"type": "string", "enum": ["credible", "uncertain", "contradicted", "unstable"]},
                    "location_id": {"type": "string", "description": "Full location_id from the list provided"},
                    "related_npc_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id_slug", "clue_text", "source_type", "reliability", "location_id", "related_npc_ids"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clues"],
    "additionalProperties": False,
}


@dataclass
class WorldContent:
    locations: list[LocationState]
    clues: list[ClueState]
    district_updates: list[DistrictState]
    npc_updates: list[NPCState]
    case_updates: list[CaseState] = field(default_factory=list)


class WorldContentGenerator:
    """Generates locations, clues, and NPC placements for a bootstrapped city."""

    def __init__(self, llm_client: SupportsJSONGeneration) -> None:
        self._llm = llm_client

    def generate(
        self,
        districts: list[DistrictState],
        npcs: list[NPCState],
        cases: list[CaseState],
        on_progress: Callable[[str], None] | None = None,
    ) -> WorldContent:
        def _emit(msg: str) -> None:
            if on_progress is not None:
                on_progress(msg)

        location_map: dict[str, LocationState] = {}
        district_updates: list[DistrictState] = []
        npc_location_map: dict[str, str] = {}  # npc_id → location_id

        # Generate locations for each district
        for district in districts:
            district_npcs = [n for n in npcs if n.district_id == district.id]
            _emit(
                f"[world] Generating locations for {district.name}"
                f" ({len(district_npcs)} NPCs to place)…"
            )
            dist_locs = self._generate_locations(district, district_npcs)
            for loc in dist_locs:
                location_map[loc.id] = loc
                for nid in loc.known_npc_ids:
                    npc_location_map[nid] = loc.id

            visible = [loc.id for loc in dist_locs if loc.access_state != "hidden"]
            hidden = [loc.id for loc in dist_locs if loc.access_state == "hidden"]
            _emit(
                f"[world]   {district.name}: {len(visible)} visible"
                f" + {len(hidden)} hidden locations"
            )
            district_updates.append(district.model_copy(update={
                "visible_locations": visible,
                "hidden_locations": hidden,
                "version": district.version + 1,
                "updated_at": TURN_ZERO,
            }))

        # Generate clues and briefings for each starting case
        clues: list[ClueState] = []
        case_updates: list[CaseState] = []
        for case in cases:
            case_locs = [loc for loc in location_map.values()
                         if loc.district_id in case.involved_district_ids]
            if not case_locs:
                case_locs = list(location_map.values())[:5]
            case_npcs = [n for n in npcs if n.district_id in case.involved_district_ids]
            _emit(f"[world] Generating clues for case: {case.title}…")
            case_clues = self._generate_clues(case, case_locs, case_npcs)
            clues.extend(case_clues)
            _emit(f"[world]   {len(case_clues)} clues generated for {case.title}")
            for clue in case_clues:
                if clue.source_id in location_map:
                    loc = location_map[clue.source_id]
                    location_map[clue.source_id] = loc.model_copy(
                        update={"clue_ids": [*loc.clue_ids, clue.id]}
                    )
            _emit(f"[world] Generating case briefing for: {case.title}…")
            briefing = self._generate_case_briefing(case, case_clues, case_npcs)
            if briefing:
                case_updates.append(case.model_copy(update={
                    "title": briefing.get("title", case.title) or case.title,
                    "discovery_hook": briefing.get("discovery_hook", "") or "",
                    "objective_summary": briefing.get("objective_summary", case.objective_summary) or case.objective_summary,
                    "updated_at": TURN_ZERO,
                }))

        # Build NPC updates: assign location_id and known_clue_ids
        npc_clue_map: dict[str, list[str]] = {}
        for clue in clues:
            for nid in clue.related_npc_ids:
                npc_clue_map.setdefault(nid, []).append(clue.id)

        npc_updates: list[NPCState] = []
        for npc in npcs:
            patch: dict[str, object] = {}
            if npc.id in npc_location_map:
                patch["location_id"] = npc_location_map[npc.id]
            if npc.id in npc_clue_map:
                patch["known_clue_ids"] = npc_clue_map[npc.id]
            if patch:
                patch["version"] = npc.version + 1
                patch["updated_at"] = TURN_ZERO
                npc_updates.append(npc.model_copy(update=patch))

        return WorldContent(
            locations=list(location_map.values()),
            clues=clues,
            district_updates=district_updates,
            npc_updates=npc_updates,
            case_updates=case_updates,
        )

    # ── Location generation ───────────────────────────────────────────────────

    def _generate_locations(
        self,
        district: DistrictState,
        district_npcs: list[NPCState],
    ) -> list[LocationState]:
        npc_lines = "\n".join(
            f"  {npc.id}: {npc.name} ({npc.role_category})" for npc in district_npcs
        ) or "  (no named NPCs)"

        system = (
            "You generate location objects for Lantern City, a noir investigative city game. "
            "Lanterns control memory and truth. Locations should feel lived-in and specific. "
            "Return valid JSON only."
        )
        user = (
            f"Generate 3–5 locations for this district.\n\n"
            f"District ID: {district.id}\n"
            f"District name: {district.name}\n"
            f"District role: {district.tone}\n"
            f"Lantern condition: {district.lantern_condition}\n"
            f"Access level: {district.current_access_level}\n\n"
            f"District social rule: {district.summary_cache.get('social_rule', 'speak carefully')}\n"
            f"Investigation pressure: {district.summary_cache.get('investigation_pressure', 'contradiction')}\n"
            f"Case-pattern biases: {', '.join(district.active_problems) if district.active_problems else 'none'}\n\n"
            f"NPCs to place (assign each to exactly one location; use exact IDs):\n{npc_lines}\n\n"
            "Rules:\n"
            "  - id_slug: unique snake_case suffix, e.g. 'archive_steps'\n"
            "  - location_type: e.g. shrine, archive, market, office, passage, ruin, hall, dock\n"
            "  - npc_ids: ONLY IDs listed above; each NPC in exactly one location\n"
            "  - scene_objects: 2–5 specific, evocative physical items\n"
            "  - is_hidden: true for at most 1 location (only if access is restricted)\n"
            "  - Make the location set reflect the district's investigation pressure and social rule, not just its name\n"
        )

        try:
            result = self._llm.generate_json(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.45,
                max_tokens=900,
                schema=_LOCATION_SCHEMA,
            )
            raw_list = result.get("locations", [])
        except Exception:
            raw_list = []

        if not raw_list:
            return self._fallback_locations(district, district_npcs)

        valid_npc_ids = {n.id for n in district_npcs}
        seen_slugs: set[str] = set()
        used_npc_ids: set[str] = set()
        out: list[LocationState] = []

        for raw in raw_list:
            slug = _slugify(str(raw.get("id_slug", "")))
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            npc_ids = [n for n in raw.get("npc_ids", [])
                       if n in valid_npc_ids and n not in used_npc_ids]
            used_npc_ids.update(npc_ids)
            is_hidden = bool(raw.get("is_hidden", False))

            out.append(LocationState(
                id=f"location_{slug}",
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                district_id=district.id,
                name=str(raw.get("name", slug.replace("_", " ").title())),
                location_type=str(raw.get("location_type", "location")),
                access_state="hidden" if is_hidden else "unknown",
                known_npc_ids=npc_ids,
                scene_objects=[str(o) for o in raw.get("scene_objects", [])],
                clue_ids=[],
            ))

        # Place any unassigned NPCs into the first location
        unplaced = [n.id for n in district_npcs if n.id not in used_npc_ids]
        if unplaced and out:
            first = out[0]
            out[0] = first.model_copy(update={"known_npc_ids": [*first.known_npc_ids, *unplaced]})

        return out or self._fallback_locations(district, district_npcs)

    # ── Clue generation ───────────────────────────────────────────────────────

    def _generate_clues(
        self,
        case: CaseState,
        locations: list[LocationState],
        npcs: list[NPCState],
    ) -> list[ClueState]:
        loc_lines = "\n".join(f"  {loc.id}: {loc.name}" for loc in locations)
        npc_lines = "\n".join(f"  {n.id}: {n.name}" for n in npcs) or "  (none)"
        case_slug = case.id.removeprefix("case_")

        system = (
            "You generate investigation clues for Lantern City, a noir investigative game. "
            "Clues are concrete pieces of evidence players discover at locations. "
            "Return valid JSON only."
        )
        user = (
            f"Generate 4–6 clues for this investigation case.\n\n"
            f"Case ID: {case.id}\n"
            f"Case title: {case.title}\n"
            f"Case type: {case.case_type}\n"
            f"Objective: {case.objective_summary}\n\n"
            f"Case pressure tags: {', '.join(case.district_effects) if case.district_effects else 'none'}\n\n"
            f"Available locations (use ONLY these exact IDs):\n{loc_lines}\n\n"
            f"Relevant NPCs (use ONLY these exact IDs):\n{npc_lines}\n\n"
            "Rules:\n"
            "  - id_slug: unique snake_case suffix, e.g. 'missing_ledger'\n"
            "  - clue_text: 1–2 concrete, atmospheric sentences\n"
            "  - source_type: document, physical, testimony, or composite\n"
            "  - reliability: credible, uncertain, contradicted, or unstable\n"
            "  - location_id: ONLY exact IDs from the location list above\n"
            "  - related_npc_ids: ONLY exact IDs from the NPC list above\n"
            "  - Reliability mix: at least 2 credible, 1–2 uncertain, 1 contradicted\n"
        )

        try:
            result = self._llm.generate_json(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.5,
                max_tokens=1100,
                schema=_CLUE_SCHEMA,
            )
            raw_list = result.get("clues", [])
        except Exception:
            return []

        valid_loc_ids = {loc.id for loc in locations}
        valid_npc_ids = {n.id for n in npcs}
        seen_slugs: set[str] = set()
        out: list[ClueState] = []

        for raw in raw_list:
            slug = _slugify(str(raw.get("id_slug", "")))
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            loc_id = str(raw.get("location_id", ""))
            if loc_id not in valid_loc_ids:
                loc_id = locations[0].id if locations else ""

            source_type = str(raw.get("source_type", "document"))
            if source_type not in _VALID_SOURCE_TYPES:
                source_type = "document"

            reliability = str(raw.get("reliability", "uncertain"))
            if reliability not in _VALID_RELIABILITIES:
                reliability = "uncertain"

            npc_ids = [n for n in raw.get("related_npc_ids", []) if n in valid_npc_ids]

            out.append(ClueState(
                id=f"clue_{case_slug}_{slug}",
                created_at=TURN_ZERO,
                updated_at=TURN_ZERO,
                source_type=source_type,
                source_id=loc_id,
                clue_text=str(raw.get("clue_text", "")),
                reliability=reliability,
                related_npc_ids=npc_ids,
                related_case_ids=[case.id],
                related_district_ids=list(case.involved_district_ids),
            ))

        return out

    # ── Case briefing ─────────────────────────────────────────────────────────

    def _generate_case_briefing(
        self,
        case: CaseState,
        clues: list[ClueState],
        npcs: list[NPCState],
    ) -> dict[str, str] | None:
        npc_lines = "\n".join(
            f"  {n.name} ({n.role_category}): {n.public_identity}" for n in npcs[:4]
        ) or "  (no named contacts)"
        clue_lines = "\n".join(
            f"  [{c.source_type}, {c.reliability}] {c.clue_text}" for c in clues[:4]
        ) or "  (no clues yet)"
        district_names = ", ".join(
            d.replace("district_", "").replace("_", " ").title()
            for d in case.involved_district_ids
        )

        system = (
            "You are writing the opening briefing for an investigation case in Lantern City, "
            "a noir city where lanterns control memory and truth. "
            "Write in second person, present tense, grounded and atmospheric. "
            "Return valid JSON only."
        )
        user = (
            "Write a case briefing for the player.\n\n"
            f"Case type: {case.case_type}\n"
            f"Involved districts: {district_names}\n"
            f"Known contacts in this case:\n{npc_lines}\n\n"
            f"Known clues (what exists in the world, not yet discovered by player):\n{clue_lines}\n\n"
            "Rules:\n"
            "- title: an evocative case name (not the ID), 4-8 words, present-tense or noun phrase\n"
            "- discovery_hook: 2-3 sentences. Establish WHO brought this to you "
            "(one of the contacts above, or an anonymous tip), WHAT they said or showed you, "
            "and WHY you can't ignore it. Write as if the player just heard this.\n"
            "- objective_summary: 1 sentence. What the player must find out or accomplish. "
            "Keep it concrete and specific — not 'investigate' but 'find out what happened to X'.\n"
            "- Do not reveal clue content directly — the discovery_hook sets atmosphere, "
            "not a data dump. The player will discover clues through play.\n"
            "- Keep language grounded, civic, noir. No magic. No fantasy clichés.\n"
        )
        try:
            result = self._llm.generate_json(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.55,
                max_tokens=600,
                schema=_CASE_BRIEFING_SCHEMA,
            )
            if isinstance(result.get("title"), str) and isinstance(result.get("discovery_hook"), str):
                return result
        except Exception:
            pass
        return None

    # ── Fallback ──────────────────────────────────────────────────────────────

    def _fallback_locations(
        self,
        district: DistrictState,
        district_npcs: list[NPCState],
    ) -> list[LocationState]:
        slug = district.id.removeprefix("district_")
        return [LocationState(
            id=f"location_{slug}_main",
            created_at=TURN_ZERO,
            updated_at=TURN_ZERO,
            district_id=district.id,
            name=district.name,
            location_type="location",
            known_npc_ids=[n.id for n in district_npcs],
            scene_objects=["lantern post", "stone pavement"],
            clue_ids=[],
        )]


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


__all__ = ["WorldContent", "WorldContentGenerator"]
