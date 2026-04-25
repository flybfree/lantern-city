from __future__ import annotations

from lantern_city.models import NPCState
from lantern_city.social import (
    append_memory_entry,
    apply_actor_relationship_shift,
    apply_player_social_consequence,
    apply_relationship_shift,
    build_conversation_memory_entry,
    run_offscreen_npc_tick,
)


def make_npc() -> NPCState:
    return NPCState(
        id="npc_ila_venn",
        created_at="turn_0",
        updated_at="turn_0",
        name="Ila Venn",
        role_category="authority",
        district_id="district_old_quarter",
        location_id="location_archive_steps",
        trust_in_player=0.15,
        suspicion=0.55,
        fear=0.42,
        loyalty="faction_memory_keepers",
        current_objective="Keep the archives orderly.",
    )


def test_build_conversation_memory_entry_keeps_social_context() -> None:
    entry = build_conversation_memory_entry(
        request_id="req_001",
        input_text="Ask who altered the ledger.",
        updated_at="turn_3",
        npc_response="Ask the annex clerk.",
        npc_exit_line="That is all I can risk saying.",
        dialogue_act="redirect_with_hint",
        npc_stance="guarded but useful",
        relationship_tag="cautious_respect",
        player_flag="asked_about_records",
        summary_text="Ila redirects the player toward the annex clerk.",
        related_case_ids=["case_missing_clerk"],
        related_clue_ids=["clue_altered_ledger"],
    )

    assert entry["memory_type"] == "conversation"
    assert entry["turn"] == "turn_3"
    assert entry["dialogue_act"] == "redirect_with_hint"
    assert entry["npc_stance"] == "guarded but useful"
    assert entry["player_flag"] == "asked_about_records"
    assert entry["related_case_ids"] == ["case_missing_clerk"]
    assert entry["related_clue_ids"] == ["clue_altered_ledger"]


def test_append_memory_entry_keeps_recent_entries_bounded() -> None:
    npc = make_npc().model_copy(
        update={
            "memory_log": [{"memory_type": "conversation", "turn": f"turn_{i}"} for i in range(12)]
        }
    )

    updated = append_memory_entry(
        npc,
        memory_entry={"memory_type": "offscreen_event", "turn": "turn_12"},
        updated_at="turn_12",
    )

    assert len(updated.memory_log) == 12
    assert updated.memory_log[0]["turn"] == "turn_1"
    assert updated.memory_log[-1]["turn"] == "turn_12"


def test_run_offscreen_npc_tick_appends_structured_offscreen_memory() -> None:
    npc = make_npc()

    result = run_offscreen_npc_tick(
        npc,
        visible_location_ids=["location_archive_steps", "location_registry_annex"],
        updated_at="turn_2",
    )

    assert result.state_changes
    assert result.npc.memory_log[-1]["memory_type"] == "offscreen_event"
    assert result.npc.memory_log[-1]["turn"] == "turn_2"
    assert result.npc.memory_log[-1]["source_actor_id"] == "world"
    assert result.npc.memory_log[-1]["offscreen_state"] == result.npc.offscreen_state
    assert result.npc.memory_log[-1]["location_id"] == result.npc.location_id


def test_apply_relationship_shift_records_status_for_player_snapshot() -> None:
    npc = make_npc()

    result = apply_relationship_shift(
        npc,
        trust_delta=0.6,
        suspicion_delta=-0.3,
        fear_delta=-0.2,
        tag="earned_trust",
        updated_at="turn_4",
    )

    snapshot = result.npc.relationships["player"]
    assert snapshot.status == "trusted"
    assert snapshot.last_updated_at == "turn_4"
    assert snapshot.last_changed_turn == "turn_4"
    assert "earned_trust" in result.npc.relationship_flags


def test_apply_actor_relationship_shift_tracks_non_player_relationships() -> None:
    npc = make_npc()

    result = apply_actor_relationship_shift(
        npc,
        actor_id="faction_memory_keepers",
        trust_delta=0.25,
        suspicion_delta=0.1,
        tag="pressured_to_comply",
        status_override="strained",
        updated_at="turn_5",
    )

    snapshot = result.npc.relationships["faction_memory_keepers"]
    assert snapshot.trust == 0.25
    assert snapshot.suspicion == 0.1
    assert snapshot.status == "strained"
    assert snapshot.last_changed_turn == "turn_5"
    assert "pressured_to_comply" in result.npc.relationship_flags


def test_run_offscreen_npc_tick_updates_loyalty_relationship_snapshot() -> None:
    npc = make_npc()

    result = run_offscreen_npc_tick(
        npc,
        visible_location_ids=["location_archive_steps", "location_registry_annex"],
        updated_at="turn_6",
    )

    loyalty = result.npc.relationships["faction_memory_keepers"]
    assert loyalty.status == "aligned"
    assert loyalty.trust >= 0.05
    assert loyalty.last_changed_turn == "turn_6"
    assert f"loyalty_{result.npc.offscreen_state}" in result.npc.relationship_flags


def test_apply_player_social_consequence_tracks_promises_and_debts() -> None:
    npc = make_npc()

    promise_result = apply_player_social_consequence(
        npc,
        player_flag="promise_made",
        player_input="I will get you a clean copy of the ledger.",
        updated_at="turn_4",
    )
    debt_result = apply_player_social_consequence(
        promise_result.npc,
        player_flag="debt_acknowledged",
        player_input="I owe you for this.",
        updated_at="turn_5",
    )

    assert promise_result.npc.known_promises
    assert "awaiting_player_promise" in promise_result.npc.relationship_flags
    assert "tracking a promise" in promise_result.state_changes[0]
    assert debt_result.npc.owed_favors
    assert "holding_player_debt" in debt_result.npc.relationship_flags


def test_run_offscreen_npc_tick_turns_unresolved_promises_into_grievances() -> None:
    npc = make_npc().model_copy(
        update={
            "known_promises": ["Player promised: I will come back with the ledger copy."],
            "relationship_flags": ["awaiting_player_promise"],
            "memory_log": [
                {
                    "memory_type": "conversation",
                    "turn": "turn_1",
                    "player_flag": "promise_made",
                    "input_text": "I will come back with the ledger copy.",
                }
            ],
        }
    )

    result = run_offscreen_npc_tick(
        npc,
        visible_location_ids=["location_archive_steps", "location_registry_annex"],
        updated_at="turn_4",
    )

    assert "Player left a promise hanging." in result.npc.grievances
    assert result.npc.offscreen_state == "waiting_on_player"
    assert any("waiting on a promise" in change for change in result.state_changes)


def test_apply_player_social_consequence_can_mark_promise_as_kept() -> None:
    npc = make_npc().model_copy(
        update={
            "known_promises": ["Player promised: I will bring the ledger copy."],
            "relationship_flags": ["awaiting_player_promise"],
        }
    )

    result = apply_player_social_consequence(
        npc,
        player_flag="promise_honored",
        player_input="As promised, I brought the ledger copy.",
        updated_at="turn_6",
    )

    assert not result.npc.known_promises
    assert "awaiting_player_promise" not in result.npc.relationship_flags
    assert result.npc.trust_in_player > npc.trust_in_player
    assert any("promise as kept" in change for change in result.state_changes)


def test_apply_player_social_consequence_can_mark_promise_as_broken() -> None:
    npc = make_npc().model_copy(
        update={
            "known_promises": ["Player promised: I will bring the ledger copy."],
            "relationship_flags": ["awaiting_player_promise"],
        }
    )

    result = apply_player_social_consequence(
        npc,
        player_flag="promise_broken",
        player_input="I couldn't get it. I broke my word.",
        updated_at="turn_6",
    )

    assert not result.npc.known_promises
    assert result.npc.grievances
    assert "broken_promise" in result.npc.relationship_flags
    assert result.npc.suspicion > npc.suspicion
    assert any("broke your word" in change for change in result.state_changes)
