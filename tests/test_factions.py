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
    )

    assert result.faction.attitude_toward_player == "guarded"
    assert "contain scrutiny in district_old_quarter" in result.faction.active_plans
    assert "manage missing clerk fallout" in result.faction.active_plans
    assert any("tightening its posture" in notice for notice in result.notices)
    assert any("now guarded toward you" in notice for notice in result.notices)
    assert any(operation.kind == "district_pressure" for operation in result.operations)
    assert any(operation.kind == "case_interference" for operation in result.operations)


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
        status="active",
        involved_district_ids=["district_old_quarter"],
        involved_faction_ids=["faction_memory_keepers"],
        npc_pressure_targets=["npc_shrine_keeper"],
    )

    result = run_faction_turn(
        faction,
        city=city,
        related_cases=[case],
        updated_at="turn_2",
        focus_district_id="district_old_quarter",
    )

    assert any(
        operation.kind == "npc_pressure" and operation.npc_id == "npc_shrine_keeper"
        for operation in result.operations
    )
