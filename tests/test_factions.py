from __future__ import annotations

from lantern_city.factions import run_faction_turn
from lantern_city.models import CaseState, CityState, FactionState


def test_run_faction_turn_tightens_posture_and_updates_attitude() -> None:
    city = CityState(
        id="city_001",
        created_at="turn_0",
        updated_at="turn_0",
        city_seed_id="seed_001",
        time_index=1,
        player_presence_level=0.2,
        active_case_ids=["case_missing_clerk"],
        district_ids=["district_old_quarter"],
        faction_ids=["faction_memory_keepers"],
    )
    faction = FactionState(
        id="faction_memory_keepers",
        created_at="turn_0",
        updated_at="turn_0",
        name="Memory Keepers",
        influence_by_district={"district_old_quarter": 0.8},
        attitude_toward_player="wary",
        active_plans=["stabilize records"],
    )
    case = CaseState(
        id="case_missing_clerk",
        created_at="turn_0",
        updated_at="turn_0",
        title="Missing Clerk",
        case_type="mystery",
        status="active",
        involved_district_ids=["district_old_quarter"],
        involved_faction_ids=["faction_memory_keepers"],
        pressure_level="rising",
        time_since_last_progress=2,
    )

    result = run_faction_turn(
        faction,
        city=city,
        related_cases=[case],
        updated_at="turn_2",
        focus_district_id="district_old_quarter",
        district_access_level="informal",
    )

    assert result.faction.attitude_toward_player == "guarded"
    assert "contain scrutiny in district_old_quarter" in result.faction.active_plans
    assert "manage missing clerk fallout" in result.faction.active_plans
    assert any("tightening its posture" in notice for notice in result.notices)
    assert any("now guarded toward you" in notice for notice in result.notices)
    assert any(operation.kind == "district_pressure" for operation in result.operations)
    assert any(operation.kind == "case_coverup" for operation in result.operations)


def test_run_faction_turn_targets_case_npc_pressure_when_available() -> None:
    city = CityState(
        id="city_001",
        created_at="turn_0",
        updated_at="turn_0",
        city_seed_id="seed_001",
        time_index=1,
        player_presence_level=0.2,
        active_case_ids=["case_generated_001"],
        district_ids=["district_old_quarter"],
        faction_ids=["faction_memory_keepers"],
    )
    faction = FactionState(
        id="faction_memory_keepers",
        created_at="turn_0",
        updated_at="turn_0",
        name="Memory Keepers",
        influence_by_district={"district_old_quarter": 0.8},
        attitude_toward_player="wary",
    )
    case = CaseState(
        id="case_generated_001",
        created_at="turn_0",
        updated_at="turn_0",
        title="Borrowed Ledger",
        case_type="mystery",
        status="escalated",
        involved_district_ids=["district_old_quarter"],
        involved_faction_ids=["faction_memory_keepers"],
        pressure_level="urgent",
        offscreen_risk_flags=["urgent_window"],
        npc_pressure_targets=["npc_shrine_keeper"],
    )

    result = run_faction_turn(
        faction,
        city=city,
        related_cases=[case],
        updated_at="turn_2",
        focus_district_id="district_old_quarter",
        district_access_level="restricted",
    )

    assert any(
        operation.kind == "npc_pressure" and operation.npc_id == "npc_shrine_keeper"
        for operation in result.operations
    )
    assert any(operation.kind == "case_coverup" for operation in result.operations)
    assert any(operation.kind == "district_surveillance" for operation in result.operations)


def test_run_faction_turn_uses_case_coverup_for_low_pressure_case() -> None:
    city = CityState(
        id="city_001",
        created_at="turn_0",
        updated_at="turn_0",
        city_seed_id="seed_001",
        time_index=1,
        player_presence_level=0.2,
        active_case_ids=["case_generated_002"],
        district_ids=["district_old_quarter"],
        faction_ids=["faction_memory_keepers"],
    )
    faction = FactionState(
        id="faction_memory_keepers",
        created_at="turn_0",
        updated_at="turn_0",
        name="Memory Keepers",
        influence_by_district={"district_old_quarter": 0.8},
        attitude_toward_player="wary",
    )
    case = CaseState(
        id="case_generated_002",
        created_at="turn_0",
        updated_at="turn_0",
        title="Quiet Ledger",
        case_type="mystery",
        status="active",
        involved_district_ids=["district_old_quarter"],
        involved_faction_ids=["faction_memory_keepers"],
        pressure_level="low",
        active_resolution_window="open",
    )

    result = run_faction_turn(
        faction,
        city=city,
        related_cases=[case],
        updated_at="turn_2",
        focus_district_id="district_old_quarter",
        district_access_level="informal",
    )

    assert any(operation.kind == "case_coverup" for operation in result.operations)
    assert not any(operation.kind == "npc_pressure" for operation in result.operations)


def test_run_faction_turn_uses_records_style_for_memory_faction() -> None:
    city = CityState(
        id="city_001",
        created_at="turn_0",
        updated_at="turn_0",
        city_seed_id="seed_001",
        time_index=1,
        player_presence_level=0.2,
        active_case_ids=["case_generated_003"],
        district_ids=["district_old_quarter"],
        faction_ids=["faction_memory_keepers"],
    )
    faction = FactionState(
        id="faction_memory_keepers",
        created_at="turn_0",
        updated_at="turn_0",
        name="Memory Keepers",
        public_goal="preserve continuity",
        hidden_goal="control what the city remembers",
        known_assets=["memory stewardship", "records", "certification"],
        active_plans=["access control", "procedural delay"],
        influence_by_district={"district_old_quarter": 0.8},
        attitude_toward_player="wary",
    )
    case = CaseState(
        id="case_generated_003",
        created_at="turn_0",
        updated_at="turn_0",
        title="Borrowed Ledger",
        case_type="mystery",
        status="active",
        involved_district_ids=["district_old_quarter"],
        involved_faction_ids=["faction_memory_keepers"],
        pressure_level="rising",
        active_resolution_window="narrowing",
    )

    result = run_faction_turn(
        faction,
        city=city,
        related_cases=[case],
        updated_at="turn_2",
        focus_district_id="district_old_quarter",
        district_access_level="informal",
    )

    assert any(operation.kind == "district_pressure" for operation in result.operations)
    assert any(operation.kind == "case_coverup" for operation in result.operations)
    assert not any(operation.kind == "case_isolation" for operation in result.operations)


def test_run_faction_turn_uses_civic_style_for_council_faction() -> None:
    city = CityState(
        id="city_001",
        created_at="turn_0",
        updated_at="turn_0",
        city_seed_id="seed_001",
        time_index=1,
        player_presence_level=0.2,
        active_case_ids=["case_generated_004"],
        district_ids=["district_lantern_ward"],
        faction_ids=["faction_council_lights"],
    )
    faction = FactionState(
        id="faction_council_lights",
        created_at="turn_0",
        updated_at="turn_0",
        name="Council of Lights",
        public_goal="maintain public order",
        hidden_goal="monopolize lantern legitimacy",
        known_assets=["civic lantern administration", "compliance", "access permits"],
        active_plans=["official review", "public reassurance"],
        influence_by_district={"district_lantern_ward": 0.8},
        attitude_toward_player="guarded",
    )
    case = CaseState(
        id="case_generated_004",
        created_at="turn_0",
        updated_at="turn_0",
        title="Night Manifest",
        case_type="mystery",
        status="active",
        involved_district_ids=["district_lantern_ward"],
        involved_faction_ids=["faction_council_lights"],
        pressure_level="rising",
        active_resolution_window="narrowing",
        npc_pressure_targets=["npc_watcher_pell"],
    )

    result = run_faction_turn(
        faction,
        city=city,
        related_cases=[case],
        updated_at="turn_2",
        focus_district_id="district_lantern_ward",
        district_access_level="informal",
    )

    assert any(operation.kind == "district_surveillance" for operation in result.operations)
    assert any(operation.kind == "case_isolation" for operation in result.operations)
