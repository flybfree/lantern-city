from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from lantern_city.active_slice import ActiveSlice
from lantern_city.generation.npc_response import (
    NPCResponseGenerationError,
    NPCResponseGenerationRequest,
    NPCResponseGenerationResult,
    NPCResponseGenerator,
)
from lantern_city.models import (
    ActiveWorkingSet,
    CityState,
    ClueState,
    DistrictState,
    NPCState,
    PlayerRequest,
    SceneState,
)


class StubLLMClient:
    def __init__(
        self,
        payload: dict[str, object] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, object]] = []

    def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        schema: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "schema": schema,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.payload is not None
        return self.payload


def make_active_slice() -> ActiveSlice:
    city = CityState(
        id="city_001",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        city_seed_id="seed_001",
    )
    district = DistrictState(
        id="district_old_quarter",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        name="Old Quarter",
        tone="hushed and procedural",
        lantern_condition="flickering",
    )
    scene = SceneState(
        id="scene_archive_talk",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        scene_type="conversation",
        location_id="location_archive_steps",
        participating_npc_ids=["npc_ila_venn"],
        immediate_goal="Find out who altered the ledger.",
    )
    npc = NPCState(
        id="npc_ila_venn",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        name="Ila Venn",
        role_category="shrine keeper",
        district_id="district_old_quarter",
        location_id="location_archive_steps",
        public_identity="Keeps the lantern records for the ward.",
        hidden_objective="Keep the annex clear of investigation.",
        current_objective="Deflect questions about the altered ledger.",
        trust_in_player=0.15,
        fear=0.42,
        suspicion=0.55,
        loyalty="Memory Keepers",
        known_clue_ids=["clue_altered_ledger"],
    )
    clue = ClueState(
        id="clue_altered_ledger",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        source_type="record",
        source_id="location_archive_steps",
        clue_text="The ledger shows two different hands on the same correction line.",
        reliability="strong",
    )
    working_set = ActiveWorkingSet(
        id="aws_001",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        city_id=city.id,
        district_id=district.id,
        scene_id=scene.id,
        npc_ids=[npc.id],
        clue_ids=[clue.id],
    )
    return ActiveSlice(
        city=city,
        working_set=working_set,
        district=district,
        location=None,
        scene=scene,
        npcs=[npc],
        clues=[clue],
        case=None,
    )


def make_player_request() -> PlayerRequest:
    return PlayerRequest(
        id="req_npc_001",
        created_at="2026-03-28T00:00:00Z",
        updated_at="2026-03-28T00:00:00Z",
        player_id="player_001",
        intent="talk_to_npc",
        target_id="npc_ila_venn",
        input_text="Ask who signed the correction after dusk.",
    )


def make_valid_payload() -> dict[str, object]:
    return {
        "task_type": "npc_response",
        "request_id": "req_npc_001",
        "summary_text": "Ila Venn deflects the question but points toward the annex clerk.",
        "structured_updates": {
            "dialogue_act": "redirect_with_hint",
            "npc_stance": "guarded but useful",
            "relationship_shift": {
                "trust_delta": 0.05,
                "suspicion_delta": 0.02,
                "fear_delta": -0.03,
                "tag": "cautious_respect",
            },
            "clue_effects": [
                {
                    "effect_type": "refine",
                    "clue_id": "clue_altered_ledger",
                    "note": "The second signature came from the annex night desk.",
                }
            ],
            "access_effects": [
                {
                    "effect_type": "soft_unlock",
                    "target_id": "location_registry_annex",
                    "note": "Ila says the night clerk may speak if approached before curfew.",
                }
            ],
            "redirect_targets": [
                {
                    "target_type": "location",
                    "target_id": "location_registry_annex",
                    "reason": "The annex night desk handled the altered page.",
                }
            ],
        },
        "cacheable_text": {
            "npc_line": "I keep the lantern ledger, not the annex hands. If you want the second signature, ask the night desk before they remember to deny it.",
            "follow_up_suggestions": [
                "Ask who was on the annex night desk.",
                "Go to the Registry Annex before curfew.",
            ],
            "exit_line_if_needed": "If that is all, the ward glass still needs tending.",
        },
        "confidence": 0.88,
        "warnings": [],
    }


def test_npc_response_generator_builds_bounded_prompt_and_returns_validated_output() -> None:
    client = StubLLMClient(make_valid_payload())
    generator = NPCResponseGenerator(client)

    result = generator.generate(
        NPCResponseGenerationRequest(
            request_id="req_npc_001",
            active_slice=make_active_slice(),
            player_request=make_player_request(),
        )
    )

    assert result.task_type == "npc_response"
    assert result.structured_updates.dialogue_act == "redirect_with_hint"
    assert result.cacheable_text.follow_up_suggestions[0].startswith("Ask who")
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 900
    assert call["schema"] is not None
    messages = call["messages"]
    assert messages[0]["role"] == "system"
    assert "one bounded npc response" in messages[0]["content"].lower()
    assert "task_type\": \"npc_response\"" in messages[1]["content"]
    assert "request_id\": \"req_npc_001\"" in messages[1]["content"]
    assert "Ila Venn" in messages[1]["content"]
    assert "Ask who signed the correction after dusk." in messages[1]["content"]
    assert "The ledger shows two different hands" in messages[1]["content"]
    assert "exactly one reply turn" in messages[1]["content"].lower()
    assert '"redirect_targets"' in messages[1]["content"]
    assert '"follow_up_suggestions"' in messages[1]["content"]


def test_npc_response_generator_wraps_llm_errors() -> None:
    client = StubLLMClient(error=ValueError("bad upstream response"))
    generator = NPCResponseGenerator(client)

    with pytest.raises(NPCResponseGenerationError, match="bad upstream response"):
        generator.generate(
            NPCResponseGenerationRequest(
                request_id="req_npc_002",
                active_slice=make_active_slice(),
                player_request=make_player_request(),
            )
        )


def test_npc_response_generator_rejects_malformed_output() -> None:
    payload = copy.deepcopy(make_valid_payload())
    del payload["cacheable_text"]["follow_up_suggestions"]
    client = StubLLMClient(payload)
    generator = NPCResponseGenerator(client)

    with pytest.raises(ValidationError, match="follow_up_suggestions"):
        generator.generate(
            NPCResponseGenerationRequest(
                request_id="req_npc_003",
                active_slice=make_active_slice(),
                player_request=make_player_request(),
            )
        )


def test_npc_response_generation_result_requires_exact_task_type() -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["task_type"] = "npc_dialogue"

    with pytest.raises(ValidationError, match="task_type"):
        NPCResponseGenerationResult.model_validate(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("summary_text", "   "),
        ("summary_text", "X" * 161),
        ("warnings", ["   "]),
        ("warnings", ["X" * 121]),
    ],
)
def test_npc_response_generation_result_rejects_unbounded_top_level_text(
    field_name: str,
    value: object,
) -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload[field_name] = value

    with pytest.raises(ValidationError, match=field_name):
        NPCResponseGenerationResult.model_validate(payload)


def test_npc_response_generation_result_rejects_transcript_like_npc_line() -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["cacheable_text"]["npc_line"] = "NPC: Ask the annex.\nPlayer: Why?"

    with pytest.raises(ValidationError, match="npc_line"):
        NPCResponseGenerationResult.model_validate(payload)


def test_npc_response_generation_result_rejects_overlong_npc_line() -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["cacheable_text"]["npc_line"] = "X" * 281

    with pytest.raises(ValidationError, match="npc_line"):
        NPCResponseGenerationResult.model_validate(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("dialogue_act", "   "),
        ("dialogue_act", "X" * 61),
        ("npc_stance", "   "),
        ("npc_stance", "X" * 81),
    ],
)
def test_npc_response_generation_result_rejects_unbounded_structured_text(
    field_name: str,
    value: str,
) -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["structured_updates"][field_name] = value

    with pytest.raises(ValidationError, match=field_name):
        NPCResponseGenerationResult.model_validate(payload)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("follow_up_suggestions", ["   "]),
        ("follow_up_suggestions", ["X" * 121]),
        ("exit_line_if_needed", "   "),
        ("exit_line_if_needed", "X" * 161),
    ],
)
def test_npc_response_generation_result_rejects_unbounded_cacheable_text(
    field_name: str,
    value: object,
) -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["cacheable_text"][field_name] = value

    with pytest.raises(ValidationError, match=field_name):
        NPCResponseGenerationResult.model_validate(payload)


@pytest.mark.parametrize(
    ("collection_name", "field_name", "value"),
    [
        ("clue_effects", "note", "   "),
        ("clue_effects", "note", "X" * 161),
        ("access_effects", "note", "   "),
        ("access_effects", "note", "X" * 161),
        ("redirect_targets", "reason", "   "),
        ("redirect_targets", "reason", "X" * 161),
    ],
)
def test_npc_response_generation_result_rejects_unbounded_effect_text(
    collection_name: str,
    field_name: str,
    value: str,
) -> None:
    payload = copy.deepcopy(make_valid_payload())
    payload["structured_updates"][collection_name][0][field_name] = value

    with pytest.raises(ValidationError, match=field_name):
        NPCResponseGenerationResult.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("structured_updates", "relationship_shift", "tag"), "   ", "tag"),
        (("structured_updates", "relationship_shift", "tag"), "X" * 81, "tag"),
        (("structured_updates", "clue_effects", 0, "effect_type"), "   ", "effect_type"),
        (("structured_updates", "clue_effects", 0, "effect_type"), "X" * 41, "effect_type"),
        (("structured_updates", "clue_effects", 0, "clue_id"), "   ", "clue_id"),
        (("structured_updates", "clue_effects", 0, "clue_id"), "mystery_001", "clue_id"),
        (("structured_updates", "clue_effects", 0, "clue_id"), "clue_" + "x" * 76, "clue_id"),
        (("structured_updates", "access_effects", 0, "effect_type"), "   ", "effect_type"),
        (("structured_updates", "access_effects", 0, "effect_type"), "X" * 41, "effect_type"),
        (("structured_updates", "access_effects", 0, "target_id"), "   ", "target_id"),
        (("structured_updates", "access_effects", 0, "target_id"), "district_old_quarter", "target_id"),
        (("structured_updates", "access_effects", 0, "target_id"), "location_" + "x" * 72, "target_id"),
        (("structured_updates", "redirect_targets", 0, "target_type"), "   ", "target_type"),
        (("structured_updates", "redirect_targets", 0, "target_type"), "X" * 41, "target_type"),
        (("structured_updates", "redirect_targets", 0, "target_id"), "   ", "target_id"),
        (("structured_updates", "redirect_targets", 0, "target_id"), "annex_001", "target_id"),
        (("structured_updates", "redirect_targets", 0, "target_id"), "location_" + "x" * 72, "target_id"),
    ],
)
def test_npc_response_generation_result_rejects_invalid_metadata_fields(
    path: tuple[object, ...],
    value: str,
    match: str,
) -> None:
    payload = copy.deepcopy(make_valid_payload())
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError, match=match):
        NPCResponseGenerationResult.model_validate(payload)


def test_npc_response_request_requires_target_npc_in_slice() -> None:
    with pytest.raises(ValueError, match="npc"):
        NPCResponseGenerationRequest(
            request_id="req_npc_004",
            active_slice=make_active_slice(),
            player_request=make_player_request(),
            npc_id="npc_unknown",
        )
