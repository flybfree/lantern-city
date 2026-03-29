# Lantern City — LLM Interface Specification

## Goal

Define a clean, provider-agnostic interface between the game runtime and the LLM used for generation.

The interface should support:
- city seed generation
- district expansion
- location expansion
- NPC response generation
- clue generation
- case fallout generation
- summary generation
- background precompute generation

## Design Principles

1. The runtime should not depend on one provider.
2. All LLM output should be shaped into structured JSON.
3. Each generation call should be narrow and task-specific.
4. The model should receive only the relevant active slice.
5. Responses should be validated before being saved.

## Recommended Abstraction

Use a single generation service interface with multiple task types.

Example task types:
- `city_seed`
- `district_expand`
- `location_expand`
- `npc_response`
- `clue_update`
- `case_fallout`
- `summary_refresh`
- `background_precompute`

## Input Contract

Every generation request should include:
- task type
- request id
- active context ids
- structured state snapshot
- user/player input if relevant
- output schema
- constraints
- generation budget

### Example request shape

```json
{
  "task_type": "npc_response",
  "request_id": "req_1001",
  "active_context": {
    "city_id": "city_001",
    "district_id": "district_old_quarter",
    "location_id": "location_shrine_lane",
    "case_id": "case_missing_clerk",
    "scene_id": "scene_014",
    "npc_id": "npc_shrine_keeper"
  },
  "player_input": "Ask about the lantern outage.",
  "state_snapshot": {
    "npc_trust": 0.56,
    "district_lantern_condition": "dim",
    "case_status": "active"
  },
  "output_schema": "npc_response_v1",
  "constraints": {
    "max_tokens": 400,
    "temperature": 0.7,
    "must_return_json": true
  }
}
```

## Output Contract

All generation results should be valid JSON and match a known schema.

### Required output fields
- `task_type`
- `request_id`
- `summary_text`
- `structured_updates`
- `cacheable_text`
- `confidence`
- `warnings`

### Example response shape

```json
{
  "task_type": "npc_response",
  "request_id": "req_1001",
  "summary_text": "The shrine keeper says the outage began before the clerk vanished.",
  "structured_updates": {
    "new_clues": ["clue_outage_before_disappearance"],
    "npc_trust_delta": 0.08,
    "case_status_change": null
  },
  "cacheable_text": {
    "npc_line": "The outage started before the clerk disappeared.",
    "follow_up_prompt": "Ask about the archive records"
  },
  "confidence": 0.84,
  "warnings": []
}
```

## Task-Specific Output Schemas

### City Seed
Should return:
- city premise
- district list
- faction list
- starting case list
- initial lantern profile
- key NPC anchors

### District Expand
Should return:
- district summary
- local problems
- major locations
- relevant NPC anchors
- rumor lines
- lantern condition

### NPC Response
Should return:
- dialogue text
- clue changes
- relationship changes
- next actions
- optional refusal or redirection

### Clue Update
Should return:
- clue text
- reliability status
- links to NPCs/cases/districts
- contradiction notes if any

### Case Fallout
Should return:
- case state changes
- district consequences
- faction reactions
- follow-up hooks

## Validation Rules

The runtime should validate output before it is committed.

Reject or repair output if:
- JSON is invalid
- required fields are missing
- the task type does not match the request
- a structured update references unknown or malformed fields
- the output is too large for the intended narrow task

## Context Budgeting

Only include the active slice of the city in the prompt.
Do not send:
- the full city
- unrelated district state
- every NPC in the world
- old generated prose that is no longer relevant

Send:
- the current case
- the relevant district or location
- the active NPCs
- the relevant clues
- the relevant lantern state
- the player’s latest action

## Provider Strategy

The runtime should wrap whatever provider is available behind a single interface.
Examples:
- OpenAI-compatible API
- local LM Studio server
- vLLM endpoint
- other OpenAI-like backends

This keeps the rest of the game independent of the model provider.

## Recommended Interface Methods

The LLM service should expose methods like:
- `generate_city_seed(context)`
- `expand_district(context)`
- `expand_location(context)`
- `respond_npc(context)`
- `update_clue(context)`
- `generate_fallout(context)`
- `refresh_summary(context)`
- `precompute_next_step(context)`

## Error Handling

If generation fails:
- retry once or twice for transient failures
- fall back to a simpler response template if needed
- avoid blocking the entire game state update

## Streaming

Streaming is optional for MVP.
If used, stream only the final prose after structured JSON validation or stream to a temporary buffer and validate on completion.

## Design Rule

The LLM should act like a narrow content generator, not like the source of truth.
The game engine owns state; the model fills in localized content.
