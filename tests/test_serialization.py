import json

import pytest

from lantern_city.models import CityState, PlayerProgressState, ScoreTier
from lantern_city.serialization import (
    deserialize_model,
    serialize_model,
    to_json_payload,
    to_json_string,
)


@pytest.fixture
def city_state() -> CityState:
    return CityState(
        id="city_001",
        created_at="turn_0",
        updated_at="turn_3",
        city_seed_id="cityseed_001",
        time_index=3,
        global_tension=0.2,
        civic_trust=0.6,
        missingness_pressure=0.35,
        active_case_ids=["case_missing_clerk"],
        district_ids=["district_old_quarter"],
        faction_ids=["faction_memory_keepers"],
        player_presence_level=0.1,
        summary_cache={"short": "The city feels tense."},
    )


@pytest.fixture
def player_progress() -> PlayerProgressState:
    return PlayerProgressState(
        id="player_progress_001",
        created_at="turn_0",
        updated_at="turn_2",
        lantern_understanding=ScoreTier(score=32, tier="Informed"),
        access=ScoreTier(score=21, tier="Restricted"),
        reputation=ScoreTier(score=18, tier="Wary"),
        leverage=ScoreTier(score=26, tier="Useful"),
        city_impact=ScoreTier(score=14, tier="Local"),
        clue_mastery=ScoreTier(score=41, tier="Competent"),
    )


def test_to_json_payload_returns_json_ready_dict(city_state: CityState) -> None:
    payload = to_json_payload(city_state)

    assert payload == city_state.model_dump(mode="json")
    assert payload["type"] == "CityState"
    json.dumps(payload)



def test_to_json_string_returns_json_text(city_state: CityState) -> None:
    text = to_json_string(city_state)

    assert json.loads(text) == city_state.model_dump(mode="json")



def test_deserialize_model_round_trips_from_dict_without_explicit_class(city_state: CityState) -> None:
    restored = deserialize_model(to_json_payload(city_state))

    assert isinstance(restored, CityState)
    assert restored == city_state



def test_deserialize_model_round_trips_from_json_string(player_progress: PlayerProgressState) -> None:
    restored = deserialize_model(to_json_string(player_progress))

    assert isinstance(restored, PlayerProgressState)
    assert restored == player_progress
    assert isinstance(restored.lantern_understanding, ScoreTier)



def test_deserialize_model_accepts_explicit_model_class(city_state: CityState) -> None:
    restored = deserialize_model(to_json_string(city_state), model_cls=CityState)

    assert isinstance(restored, CityState)
    assert restored == city_state



def test_deserialize_model_rejects_unknown_runtime_type() -> None:
    with pytest.raises(ValueError, match="Unknown model type"):
        deserialize_model(
            {
                "id": "mystery_001",
                "type": "UnknownState",
                "version": 1,
                "created_at": "turn_0",
                "updated_at": "turn_0",
            }
        )



def test_deserialize_model_rejects_type_mismatch_for_explicit_model_class() -> None:
    payload = {
        "id": "city_001",
        "type": "CityState",
        "version": 1,
        "created_at": "turn_0",
        "updated_at": "turn_0",
        "city_seed_id": "cityseed_001",
    }

    with pytest.raises(ValueError, match="does not match requested model class"):
        deserialize_model(payload, model_cls=PlayerProgressState)



def test_serialize_model_rejects_non_pydantic_objects() -> None:
    with pytest.raises(TypeError, match="Pydantic model"):
        serialize_model({"type": "CityState"})
