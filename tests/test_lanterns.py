from __future__ import annotations

import pytest

from pydantic import ValidationError

from lantern_city.clues import create_clue
from lantern_city.lanterns import (
    LanternRuleProfile,
    apply_lantern_to_clue,
    assess_access,
    assess_memory,
    assess_witness_confidence,
)

TURN_ONE = "turn_1"


def test_bright_lantern_supports_witness_confidence_and_memory() -> None:
    profile = LanternRuleProfile(state="bright", missingness="low")

    confidence = assess_witness_confidence(profile, corroborated=True, direct_experience=True)
    memory = assess_memory(profile)

    assert confidence == "strong"
    assert memory == "anchored"


def test_extinguished_lantern_blocks_formal_access_but_unofficial_routes_can_still_help() -> None:
    profile = LanternRuleProfile(state="extinguished", missingness="medium")

    formal = assess_access(profile, required_access="restricted", formal=True)
    unofficial = assess_access(profile, required_access="restricted", formal=False, leverage_tier=2)

    assert formal == "blocked"
    assert unofficial == "contested"


def test_bright_lantern_does_not_grant_universal_secret_access() -> None:
    profile = LanternRuleProfile(state="bright", missingness="none")

    public_formal = assess_access(profile, required_access="public", formal=True)
    restricted_formal = assess_access(profile, required_access="restricted", formal=True)
    trusted_formal = assess_access(
        profile,
        required_access="trusted",
        formal=True,
        reputation_tier=1,
    )
    secret_formal = assess_access(
        profile,
        required_access="secret",
        formal=True,
        reputation_tier=3,
        leverage_tier=1,
    )

    assert public_formal == "open"
    assert restricted_formal == "open"
    assert trusted_formal == "contested"
    assert secret_formal == "blocked"


def test_altered_lantern_requires_documented_fields() -> None:
    with pytest.raises(ValidationError, match="altered_target_domain"):
        LanternRuleProfile(state="altered", missingness="medium")


def test_altered_lantern_rejects_unknown_mvp_values() -> None:
    with pytest.raises(ValidationError, match="altered_effect_mode"):
        LanternRuleProfile(
            state="altered",
            missingness="medium",
            altered_target_domain="records",
            altered_effect_mode="warp",
            altered_scope="route",
        )


def test_flickering_lantern_and_pressure_degrade_testimony_more_than_physical_evidence() -> None:
    profile = LanternRuleProfile(state="flickering", missingness="high")
    testimony = create_clue(
        clue_id="clue_testimony",
        source_type="testimony",
        source_id="npc_01",
        clue_text="I saw the clerk enter the bell house.",
        reliability="credible",
        created_at=TURN_ONE,
    )
    physical = create_clue(
        clue_id="clue_physical",
        source_type="physical",
        source_id="scene_01",
        clue_text="Wet ash sits in the bell house lock.",
        reliability="credible",
        created_at=TURN_ONE,
    )

    degraded_testimony = apply_lantern_to_clue(testimony, profile, updated_at="turn_2")
    degraded_physical = apply_lantern_to_clue(physical, profile, updated_at="turn_2")

    assert degraded_testimony.reliability == "unstable"
    assert degraded_physical.reliability == "uncertain"


def test_altered_lantern_only_penalizes_the_target_domain() -> None:
    profile = LanternRuleProfile(
        state="altered",
        missingness="medium",
        altered_target_domain="records",
        altered_effect_mode="suppress",
        altered_scope="route",
    )
    record_clue = create_clue(
        clue_id="clue_record",
        source_type="document",
        source_id="ledger_09",
        clue_text="The clerk's entry vanishes between copies.",
        reliability="credible",
        created_at=TURN_ONE,
    )
    testimony_clue = create_clue(
        clue_id="clue_talk",
        source_type="testimony",
        source_id="npc_02",
        clue_text="The bell-ringer remembers hearing the clerk argue.",
        reliability="credible",
        created_at=TURN_ONE,
    )

    altered_record = apply_lantern_to_clue(record_clue, profile, updated_at="turn_2")
    altered_testimony = apply_lantern_to_clue(testimony_clue, profile, updated_at="turn_2")

    assert altered_record.reliability == "distorted"
    assert altered_testimony.reliability == "credible"
