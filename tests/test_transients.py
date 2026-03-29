from __future__ import annotations

import random

import pytest

from lantern_city.transients import TransientEncounter, roll_encounter


def _seeded_rng(seed: int) -> random.Random:
    return random.Random(seed)


def test_roll_encounter_returns_none_at_low_probability() -> None:
    # With a seed that produces r.random() > 0.30, should return None
    # Use a very high starting value by forcing all trials
    none_count = sum(
        1
        for seed in range(200)
        if roll_encounter("district_old_quarter", rng=_seeded_rng(seed)) is None
    )
    # Roughly 70% should be None given 30% chance
    assert none_count > 100


def test_roll_encounter_returns_encounter_within_chance() -> None:
    hit_count = sum(
        1
        for seed in range(500)
        if roll_encounter("district_old_quarter", rng=_seeded_rng(seed)) is not None
    )
    # Should be roughly 150 ± generous margin
    assert 80 < hit_count < 250


def test_roll_encounter_returns_none_for_unknown_district() -> None:
    # Even if random chance passes, unknown district has no pool
    rng = _seeded_rng(42)
    # Force chance to pass by patching nothing — unknown district exits early
    results = [
        roll_encounter("district_nonexistent", rng=_seeded_rng(seed))
        for seed in range(100)
    ]
    assert all(r is None for r in results)


def test_roll_encounter_fields_are_populated() -> None:
    # Find a seed that produces an encounter
    for seed in range(1000):
        enc = roll_encounter("district_old_quarter", rng=_seeded_rng(seed))
        if enc is not None:
            assert enc.archetype
            assert enc.narrative
            assert enc.effect_reason
            assert isinstance(enc.effect_amount, int)
            assert enc.effect_track is None or isinstance(enc.effect_track, str)
            return
    pytest.fail("No encounter produced in 1000 seeds")


def test_roll_encounter_covers_all_seeded_districts() -> None:
    districts = [
        "district_old_quarter",
        "district_lantern_ward",
        "district_the_docks",
        "district_market_spires",
        "district_salt_barrens",
        "district_underways",
    ]
    for district_id in districts:
        found = False
        for seed in range(500):
            enc = roll_encounter(district_id, rng=_seeded_rng(seed))
            if enc is not None:
                assert enc.archetype
                assert enc.narrative
                found = True
                break
        assert found, f"No encounter produced for {district_id}"


def test_roll_encounter_negative_effect_is_small() -> None:
    for seed in range(2000):
        enc = roll_encounter("district_lantern_ward", rng=_seeded_rng(seed))
        if enc is not None and enc.effect_amount < 0:
            assert enc.effect_amount >= -3, "Effect should never be a large penalty"
            return


def test_roll_encounter_positive_effect_is_small() -> None:
    for seed in range(2000):
        enc = roll_encounter("district_old_quarter", rng=_seeded_rng(seed))
        if enc is not None and enc.effect_amount > 0:
            assert enc.effect_amount <= 3, "Effect should never be a large gain"
            return


def test_transient_encounter_is_frozen() -> None:
    for seed in range(500):
        enc = roll_encounter("district_the_docks", rng=_seeded_rng(seed))
        if enc is not None:
            with pytest.raises((AttributeError, TypeError)):
                enc.narrative = "mutated"  # type: ignore[misc]
            return
