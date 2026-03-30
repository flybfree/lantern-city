"""City generation validator for Lantern City.

Usage:
    uv run python validate_city.py [path/to/lantern-city.sqlite3]

Loads the database, checks every generated object for completeness and
cross-reference integrity, and prints a structured report.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on the path when run from the project root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lantern_city.models import (
    ActiveWorkingSet,
    CaseState,
    ClueState,
    CityState,
    DistrictState,
    FactionState,
    LocationState,
    NPCState,
    PlayerProgressState,
)
from lantern_city.store import SQLiteStore

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OK = "  \033[32m[OK]\033[0m"
WARN = "  \033[33m[!!]\033[0m"
FAIL = "  \033[31m[XX]\033[0m"
SECTION = "\033[1;34m"
RESET = "\033[0m"


def section(title: str) -> None:
    print(f"\n{SECTION}-- {title} {RESET}")


def check(label: str, passed: bool, detail: str = "") -> bool:
    icon = OK if passed else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"{icon} {label}{suffix}")
    return passed


def warn(label: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"{WARN} {label}{suffix}")


def run(db_path: Path) -> int:
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    store = SQLiteStore(db_path)
    failures = 0

    # ── City ────────────────────────────────────────────────────────────────
    section("City")
    cities = store.list_objects("CityState")
    if not check("CityState exists", len(cities) == 1, f"{len(cities)} found"):
        print("  Cannot continue — no city in database.")
        return 1

    city = cities[0]
    assert isinstance(city, CityState)
    print(f"     id: {city.id}")
    print(f"     districts: {len(city.district_ids)}")
    print(f"     active cases: {len(city.active_case_ids)}")
    print(f"     global tension: {city.global_tension:.2f}")
    print(f"     missingness pressure: {city.missingness_pressure:.2f}")

    if not check("has districts", len(city.district_ids) > 0):
        failures += 1
    if not check("has active cases", len(city.active_case_ids) > 0):
        failures += 1

    # ── Districts ────────────────────────────────────────────────────────────
    section("Districts")
    district_map: dict[str, DistrictState] = {}
    for did in city.district_ids:
        obj = store.load_object("DistrictState", did)
        if not isinstance(obj, DistrictState):
            print(f"{FAIL} {did}  (missing from store)")
            failures += 1
            continue
        district_map[did] = obj
        has_locs = len(obj.visible_locations) > 0
        flag = OK if has_locs else FAIL
        if not has_locs:
            failures += 1
        print(f"{flag} {obj.name} ({did})")
        print(f"       lantern: {obj.lantern_condition}  |  stability: {obj.stability:.2f}")
        print(f"       visible locations: {len(obj.visible_locations)}  hidden: {len(obj.hidden_locations)}")

    # ── Factions ─────────────────────────────────────────────────────────────
    section("Factions")
    factions = store.list_objects("FactionState")
    if not check("has factions", len(factions) > 0, f"{len(factions)} found"):
        failures += 1
    for f in factions:
        assert isinstance(f, FactionState)
        covered = set(f.influence_by_district) == set(city.district_ids)
        icon = OK if covered else WARN
        suffix = "" if covered else f"missing districts: {set(city.district_ids) - set(f.influence_by_district)}"
        print(f"{icon} {f.name} ({f.id})  attitude: {f.attitude_toward_player}")
        if suffix:
            print(f"     {suffix}")

    # ── Locations ────────────────────────────────────────────────────────────
    section("Locations")
    all_location_ids: set[str] = set()
    for district in district_map.values():
        all_location_ids.update(district.visible_locations)
        all_location_ids.update(district.hidden_locations)

    location_map: dict[str, LocationState] = {}
    for loc_id in sorted(all_location_ids):
        obj = store.load_object("LocationState", loc_id)
        if not isinstance(obj, LocationState):
            print(f"{FAIL} {loc_id}  (missing from store)")
            failures += 1
            continue
        location_map[loc_id] = obj

    total_locs = len(location_map)
    total_clue_refs = sum(len(loc.clue_ids) for loc in location_map.values())
    total_npc_refs = sum(len(loc.known_npc_ids) for loc in location_map.values())
    print(f"{OK} {total_locs} locations loaded across all districts")
    print(f"     clue references: {total_clue_refs}  |  NPC references: {total_npc_refs}")

    empty_locs = [loc.name for loc in location_map.values() if not loc.known_npc_ids and not loc.clue_ids]
    if empty_locs:
        warn(f"{len(empty_locs)} locations with no NPCs and no clues", ", ".join(empty_locs))

    # ── NPCs ─────────────────────────────────────────────────────────────────
    section("NPCs")
    npcs = store.list_objects("NPCState")
    npcs = [n for n in npcs if isinstance(n, NPCState)]
    check("has NPCs", len(npcs) > 0, f"{len(npcs)} found")

    unplaced = [n for n in npcs if n.location_id == "location_tbd" or not n.location_id]
    placed = [n for n in npcs if n.location_id and n.location_id != "location_tbd"]

    if not check("all NPCs placed in locations", len(unplaced) == 0,
                 f"{len(unplaced)} still at location_tbd"):
        failures += 1
        for n in unplaced:
            print(f"     {FAIL} {n.name} ({n.id}) in {n.district_id}")

    for npc in placed:
        loc_exists = npc.location_id in location_map
        if not loc_exists:
            print(f"{FAIL} {npc.name} ({npc.id}) points to missing location: {npc.location_id}")
            failures += 1

    print(f"{OK} {len(placed)}/{len(npcs)} NPCs placed")
    for npc in sorted(npcs, key=lambda n: n.district_id or ""):
        clue_count = len(npc.known_clue_ids)
        loc_label = npc.location_id if npc.location_id else "—"
        print(f"     {npc.name} ({npc.id})  loc: {loc_label}  known clues: {clue_count}")

    # ── Cases ────────────────────────────────────────────────────────────────
    section("Cases")
    case_map: dict[str, CaseState] = {}
    for cid in city.active_case_ids:
        obj = store.load_object("CaseState", cid)
        if not isinstance(obj, CaseState):
            print(f"{FAIL} {cid}  (missing from store)")
            failures += 1
            continue
        case_map[cid] = obj

    for case in case_map.values():
        print(f"{OK} {case.title} ({case.id})  status: {case.status}")
        print(f"     type: {case.case_type}  |  intensity: {getattr(case, 'intensity', '—')}")
        print(f"     districts: {case.involved_district_ids}")
        print(f"     factions:  {case.involved_faction_ids}")
        print(f"     key NPCs:  {case.involved_npc_ids}")
        has_summary = bool(case.objective_summary)
        if not check("  has objective_summary", has_summary):
            failures += 1

    # ── Clues ────────────────────────────────────────────────────────────────
    section("Clues")
    clues = store.list_objects("ClueState")
    clues = [c for c in clues if isinstance(c, ClueState)]
    check("has clues", len(clues) > 0, f"{len(clues)} found")

    valid_reliabilities = {"credible", "uncertain", "contradicted", "unstable", "solid", "discredited"}
    valid_source_types = {"document", "physical", "testimony", "composite"}

    bad_reliability = [c for c in clues if c.reliability not in valid_reliabilities]
    bad_source_type = [c for c in clues if c.source_type not in valid_source_types]
    empty_text = [c for c in clues if not c.clue_text.strip()]
    orphaned = [c for c in clues if not c.related_case_ids]

    if not check("all clues have valid reliability", len(bad_reliability) == 0,
                 f"{len(bad_reliability)} invalid"):
        failures += 1
        for c in bad_reliability:
            print(f"     {FAIL} {c.id}: '{c.reliability}'")

    if not check("all clues have valid source_type", len(bad_source_type) == 0,
                 f"{len(bad_source_type)} invalid"):
        failures += 1

    if not check("all clues have text", len(empty_text) == 0,
                 f"{len(empty_text)} empty"):
        failures += 1

    if orphaned:
        warn(f"{len(orphaned)} clues with no related_case_ids")

    reliability_counts: dict[str, int] = {}
    for c in clues:
        reliability_counts[c.reliability] = reliability_counts.get(c.reliability, 0) + 1
    print(f"     reliability breakdown: {reliability_counts}")

    for clue in clues:
        src_ok = clue.source_id in location_map or clue.source_id in district_map
        icon = OK if src_ok else WARN
        case_label = clue.related_case_ids[0] if clue.related_case_ids else "—"
        print(f"{icon} [{clue.reliability:12s}] {clue.id}")
        print(f"       source: {clue.source_id}  |  case: {case_label}")
        if clue.clue_text:
            excerpt = clue.clue_text[:80].replace("\n", " ")
            print(f"       \"{excerpt}{'…' if len(clue.clue_text) > 80 else ''}\"")

    # ── Progression ──────────────────────────────────────────────────────────
    section("Player Progression")
    progress_items = store.list_objects("PlayerProgressState")
    if not check("PlayerProgressState exists", len(progress_items) == 1,
                 f"{len(progress_items)} found"):
        failures += 1
    else:
        p = progress_items[0]
        assert isinstance(p, PlayerProgressState)
        for track in ("lantern_understanding", "access", "reputation", "leverage", "city_impact", "clue_mastery"):
            score_tier = getattr(p, track)
            print(f"     {track}: {score_tier.score} ({score_tier.tier})")

    # ── Cross-references ─────────────────────────────────────────────────────
    section("Cross-reference integrity")
    all_npc_ids = {n.id for n in npcs}
    all_case_ids = set(city.active_case_ids)

    # Cases reference valid NPCs
    for case in case_map.values():
        bad_npcs = set(case.involved_npc_ids) - all_npc_ids
        if bad_npcs:
            print(f"{FAIL} Case {case.id} references unknown NPCs: {bad_npcs}")
            failures += 1

    # Location NPC refs valid
    bad_loc_npc_refs = 0
    for loc in location_map.values():
        for nid in loc.known_npc_ids:
            if nid not in all_npc_ids:
                bad_loc_npc_refs += 1
    if not check("location NPC refs all valid", bad_loc_npc_refs == 0,
                 f"{bad_loc_npc_refs} dangling"):
        failures += 1

    # Clue case refs valid
    bad_clue_case_refs = sum(
        1 for c in clues
        for cid in c.related_case_ids
        if cid not in all_case_ids
    )
    if not check("clue case refs all valid", bad_clue_case_refs == 0,
                 f"{bad_clue_case_refs} dangling"):
        failures += 1

    # ── Summary ──────────────────────────────────────────────────────────────
    section("Summary")
    print(f"     City:      {city.id}")
    print(f"     Districts: {len(district_map)}")
    print(f"     Factions:  {len(factions)}")
    print(f"     Locations: {total_locs}")
    print(f"     NPCs:      {len(npcs)}  (placed: {len(placed)})")
    print(f"     Cases:     {len(case_map)}")
    print(f"     Clues:     {len(clues)}")

    print()
    if failures == 0:
        print(f"\033[32m✓ All checks passed.\033[0m\n")
        return 0
    else:
        print(f"\033[31m✗ {failures} check(s) failed.\033[0m\n")
        return 1


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("lantern-city.sqlite3")
    sys.exit(run(path))
