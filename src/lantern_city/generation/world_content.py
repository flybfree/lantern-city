"""World content generation for Lantern City.

Given a bootstrapped city (districts, NPCs, cases), generates:
  - Locations for each district (3–5 per district)
  - Clues for each starting case (4–6 clues across relevant locations)
  - Resolution paths for each starting case (2–4 paths, priority-ordered)
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
_VALID_OUTCOME_STATUSES = frozenset({"solved", "partially solved", "failed"})

_RESOLUTION_PATHS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resolution_paths": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "priority": {"type": "integer", "description": "1 = best outcome checked first, higher = worse fallback"},
                    "path_id": {"type": "string", "description": "snake_case label, e.g. 'clean_exposure'"},
                    "label": {"type": "string", "description": "Short human-readable label"},
                    "outcome_status": {"type": "string", "enum": ["solved", "partially solved", "failed"]},
                    "required_clue_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exact clue IDs from the list provided that must be credible for this path",
                    },
                    "required_credible_count": {"type": "integer", "description": "Minimum credible clues from required_clue_ids needed"},
                    "summary_text": {"type": "string", "description": "2-3 sentences: what happened when this path resolves"},
                    "fallout_text": {"type": "string", "description": "1-2 sentences: city/district consequences"},
                },
                "required": ["priority", "path_id", "label", "outcome_status", "required_clue_ids", "required_credible_count", "summary_text", "fallout_text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["resolution_paths"],
    "additionalProperties": False,
}


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
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 investigative questions the player must answer — 'Who...?', 'Where...?', 'Why...?' — not clue text",
        },
    },
    "required": ["title", "discovery_hook", "objective_summary", "open_questions"],
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
            hook_npc = _pick_hook_npc(case_npcs, case_clues, npc_location_map)
            _emit(f"[world] Generating case briefing for: {case.title}…")
            briefing = self._generate_case_briefing(case, case_clues, case_npcs, hook_npc=hook_npc)
            _emit(f"[world] Generating resolution paths for: {case.title}…")
            resolution_conditions = self._generate_resolution_paths(case, case_clues, case_npcs)
            _emit(f"[world]   {len(resolution_conditions)} resolution paths generated")
            case_patch: dict[str, object] = {"updated_at": TURN_ZERO}
            if hook_npc is not None:
                case_patch["hook_npc_id"] = hook_npc.id
            if briefing:
                case_patch["title"] = briefing.get("title", case.title) or case.title
                case_patch["discovery_hook"] = briefing.get("discovery_hook", "") or ""
                case_patch["objective_summary"] = briefing.get("objective_summary", case.objective_summary) or case.objective_summary
                raw_questions = briefing.get("open_questions") or []
                cleaned_questions = [q.strip()[:200] for q in raw_questions if isinstance(q, str) and q.strip()]
                if cleaned_questions:
                    case_patch["open_questions"] = cleaned_questions[:5]
            if resolution_conditions:
                case_patch["resolution_conditions"] = resolution_conditions
            if len(case_patch) > 1:
                case_updates.append(case.model_copy(update=case_patch))

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
            f"  {npc.id}: {npc.name} ({npc.role_category})"
            + (f" — place in or near a {npc.location_type_hint}" if npc.location_type_hint else "")
            for npc in district_npcs
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

        out = _enforce_reliability_mix(out)
        return out

    # ── Resolution paths ──────────────────────────────────────────────────────

    def _generate_resolution_paths(
        self,
        case: CaseState,
        clues: list[ClueState],
        npcs: list[NPCState],
    ) -> list[dict]:
        clue_lines = "\n".join(
            f"  {c.id}: [{c.source_type}, {c.reliability}] {c.clue_text}" for c in clues
        ) or "  (no clues)"
        npc_lines = "\n".join(
            f"  {n.name} ({n.role_category})" for n in npcs[:4]
        ) or "  (none)"

        system = (
            "You are designing investigation resolution paths for Lantern City, a noir game. "
            "Resolution paths are checked priority-1-first; the last must always be reachable (required_credible_count: 0). "
            "Return valid JSON only."
        )
        user = (
            f"Generate 3 resolution paths for this case.\n\n"
            f"Case title: {case.title}\n"
            f"Objective: {case.objective_summary}\n\n"
            f"Available clues (use ONLY these exact IDs in required_clue_ids):\n{clue_lines}\n\n"
            f"Key NPCs:\n{npc_lines}\n\n"
            "Rules:\n"
            "  - priority 1: best outcome ('solved'), requires the most credible clues (2–3 specific IDs)\n"
            "  - priority 2: partial outcome ('partially solved'), requires 1–2 credible clues\n"
            "  - priority 3: fallback ('failed'), required_credible_count must be 0 so it always triggers\n"
            "  - required_clue_ids: subset of exact IDs listed above\n"
            "  - required_credible_count: how many from required_clue_ids must be credible\n"
            "  - summary_text: 2-3 sentences of what happens when this path resolves\n"
            "  - fallout_text: 1-2 sentences of lasting city/district consequence\n"
            "  - path_id: unique snake_case, e.g. 'clean_exposure', 'quiet_resolution', 'burial'\n"
        )
        try:
            result = self._llm.generate_json(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.4,
                max_tokens=1200,
                schema=_RESOLUTION_PATHS_SCHEMA,
            )
            raw_paths = result.get("resolution_paths", [])
        except Exception:
            return _fallback_resolution_paths(clues)

        valid_clue_ids = {c.id for c in clues}
        out: list[dict] = []
        seen_ids: set[str] = set()

        for raw in raw_paths:
            path_id = str(raw.get("path_id", "")).strip()
            if not path_id or path_id in seen_ids:
                continue
            seen_ids.add(path_id)

            outcome = str(raw.get("outcome_status", "failed"))
            if outcome not in _VALID_OUTCOME_STATUSES:
                outcome = "failed"

            required_ids = [cid for cid in raw.get("required_clue_ids", []) if cid in valid_clue_ids]
            required_count = max(0, int(raw.get("required_credible_count", 0)))
            # Fallback path must always be reachable
            if int(raw.get("priority", 99)) >= 3:
                required_count = 0
                required_ids = []

            out.append({
                "priority": int(raw.get("priority", len(out) + 1)),
                "path_id": path_id,
                "label": str(raw.get("label", path_id.replace("_", " ").title()))[:80],
                "outcome_status": outcome,
                "required_clue_ids": required_ids,
                "required_credible_count": required_count,
                "summary_text": str(raw.get("summary_text", "Case resolved."))[:400],
                "fallout_text": str(raw.get("fallout_text", ""))[:300],
            })

        if not out:
            return _fallback_resolution_paths(clues)

        # Ensure there's always a reachable fallback
        if not any(p["required_credible_count"] == 0 for p in out):
            out.append({
                "priority": max(p["priority"] for p in out) + 1,
                "path_id": "burial",
                "label": "Burial",
                "outcome_status": "failed",
                "required_clue_ids": [],
                "required_credible_count": 0,
                "summary_text": "The investigation closed without enough evidence. The official account held.",
                "fallout_text": "District stability superficially restored. Truth buried.",
            })

        return sorted(out, key=lambda p: p["priority"])

    # ── Case briefing ─────────────────────────────────────────────────────────

    def _generate_case_briefing(
        self,
        case: CaseState,
        clues: list[ClueState],
        npcs: list[NPCState],
        *,
        hook_npc: NPCState | None = None,
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
        hook_instruction = (
            f"- discovery_hook: 2-3 sentences spoken or implied by {hook_npc.name} "
            f"({hook_npc.role_category}). Write what they say or show the player — "
            "grounded in their role, not a summary. Write as if the player just heard this.\n"
        ) if hook_npc else (
            "- discovery_hook: 2-3 sentences. Establish WHO brought this to you "
            "(one of the contacts above, or an anonymous tip), WHAT they said or showed you, "
            "and WHY you can't ignore it. Write as if the player just heard this.\n"
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
            f"{hook_instruction}"
            "- objective_summary: 1 sentence. What the player must find out or accomplish. "
            "Keep it concrete and specific — not 'investigate' but 'find out what happened to X'.\n"
            "- open_questions: 3-5 investigative questions the player must answer to resolve the case. "
            "Frame each as 'Who...?', 'Where...?', 'Why...?', or 'What...?' — "
            "questions that map to what the resolution paths need to establish. "
            "Do NOT copy clue text; write the questions the player is trying to answer.\n"
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


_HOOK_ROLE_PRIORITY = {"informant": 0, "witness": 1, "gatekeeper": 2, "suspect": 3, "authority": 4}


def _pick_hook_npc(
    case_npcs: list[NPCState],
    case_clues: list[ClueState],
    npc_location_map: dict[str, str],
) -> NPCState | None:
    """Pick the NPC who will surface the case through conversation.

    Prefers placed NPCs (have a location) with informant/witness roles, then by
    how many case clues they're linked to. Falls back to any placed NPC, then
    first NPC overall.
    """
    if not case_npcs:
        return None

    clue_npc_counts: dict[str, int] = {}
    for clue in case_clues:
        for nid in clue.related_npc_ids:
            clue_npc_counts[nid] = clue_npc_counts.get(nid, 0) + 1

    placed = [n for n in case_npcs if n.id in npc_location_map]
    candidates = placed or case_npcs

    return min(
        candidates,
        key=lambda n: (
            _HOOK_ROLE_PRIORITY.get(n.role_category, 5),
            -clue_npc_counts.get(n.id, 0),
        ),
    )


def _fallback_resolution_paths(clues: list[ClueState]) -> list[dict]:
    credible_ids = [c.id for c in clues if c.reliability == "credible"][:2]
    paths: list[dict] = []
    if credible_ids:
        paths.append({
            "priority": 1,
            "path_id": "evidence_assembled",
            "label": "Evidence Assembled",
            "outcome_status": "solved",
            "required_clue_ids": credible_ids,
            "required_credible_count": len(credible_ids),
            "summary_text": "The credible evidence was assembled and presented. The case closed with enough truth on the record.",
            "fallout_text": "The district carries a recoverable scar. The city moves on.",
        })
    any_ids = [c.id for c in clues[:1]]
    paths.append({
        "priority": 2,
        "path_id": "partial_resolution",
        "label": "Partial Resolution",
        "outcome_status": "partially solved",
        "required_clue_ids": any_ids,
        "required_credible_count": 1 if any_ids else 0,
        "summary_text": "Some evidence surfaced but not enough for a complete resolution. The situation stabilised without full clarity.",
        "fallout_text": "The case closes without a full answer. Related pressure may resurface.",
    })
    paths.append({
        "priority": 3,
        "path_id": "burial",
        "label": "Burial",
        "outcome_status": "failed",
        "required_clue_ids": [],
        "required_credible_count": 0,
        "summary_text": "The investigation produced insufficient evidence. The official account hardened.",
        "fallout_text": "Truth buried. Missingness pressure increases.",
    })
    return paths


_CREDIBLE_SET = frozenset({"credible", "solid"})
_NON_TESTIMONY_SOURCES = frozenset({"document", "physical", "composite"})
_PROMOTION_ORDER = ("uncertain", "unstable", "contradicted")


def _enforce_reliability_mix(clues: list[ClueState]) -> list[ClueState]:
    """Guarantee at least 2 credible/solid clues without destroying fragile ones.

    The LLM is instructed to produce 2+ credible clues but doesn't always comply.
    We promote non-testimony clues (physical/document/composite) first, since those
    can also be upgraded later via physical discovery. Testimony clues are left alone
    because NPC dialogue is their natural upgrade path.
    """
    if not clues:
        return clues

    credible_count = sum(1 for c in clues if c.reliability in _CREDIBLE_SET)
    needed = max(0, 2 - credible_count)
    if needed == 0:
        return clues

    # Candidates: non-testimony clues not already credible, ordered by promotion priority
    candidates = [
        i for i, c in enumerate(clues)
        if c.source_type in _NON_TESTIMONY_SOURCES and c.reliability not in _CREDIBLE_SET
    ]

    result = list(clues)
    promoted = 0
    for idx in candidates:
        if promoted >= needed:
            break
        result[idx] = result[idx].model_copy(update={"reliability": "credible"})
        promoted += 1

    # If we still need credible clues and only testimony clues remain, promote one
    if promoted < needed:
        for i, c in enumerate(result):
            if promoted >= needed:
                break
            if c.reliability not in _CREDIBLE_SET:
                result[i] = c.model_copy(update={"reliability": "credible"})
                promoted += 1

    return result


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


__all__ = ["WorldContent", "WorldContentGenerator"]
