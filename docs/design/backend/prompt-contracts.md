# Lantern City — Prompt Contracts

## Purpose

This document defines the prompt-contract layer for Lantern City’s generation system.
It translates the abstract LLM interface into concrete task rules for the MVP.

These contracts exist so that generation is:
- narrow
- repeatable
- repairable
- bounded in output size
- aligned with engine-owned state

This document should be treated as the operational companion to:
- `backend/llm-interface-spec.md`
- `backend/city-seed-schema.md`
- `mechanics/player-interaction-model.md`
- `mechanics/request-lifecycle.md`
- `mechanics/lantern-and-missingness-rules.md`

## Core Contract Philosophy

The LLM is never the source of truth.
The engine is the source of truth.

The LLM is allowed to:
- produce localized prose
- fill in constrained structured content
- propose clue phrasing, summaries, reactions, and scene details
- express already-allowed consequences in flavorful language

The LLM is not allowed to:
- invent persistent state outside the provided schema
- override known world facts
- introduce new factions, districts, or mechanics unless explicitly requested
- expand the scope of a task beyond the requested slice
- decide hidden rules of lanterns or Missingness on its own
- silently resolve major case questions without the required evidence state

## Universal Prompt Contract

Every prompt contract should be built from the same logical sections.

1. Task instruction
2. World rules and non-negotiables
3. Active context slice
4. Task-specific schema
5. Output constraints
6. Forbidden behaviors
7. Validation and repair guidance

## Universal Non-Negotiables

These rules should appear in some form for every generation task.

- The game engine owns all persistent state.
- Use only the entities, IDs, and world facts provided in the context packet.
- Do not invent additional persistent facts unless the task explicitly asks for new local content objects.
- Keep output within the requested task scope.
- Respect Lantern City tone: noir, wet, restrained, civic, eerie, legible.
- Preserve mystery through implication, not confusion.
- Return valid JSON only.
- If information is missing, use a warning field rather than inventing unsupported certainty.

## Shared JSON Envelope

All task responses should fit this shared envelope.
Task-specific inner fields may vary, but the top-level contract remains stable.

```json
{
  "task_type": "npc_response",
  "request_id": "req_1001",
  "summary_text": "Short plain-language summary of the result.",
  "structured_updates": {},
  "cacheable_text": {},
  "confidence": 0.0,
  "warnings": []
}
```

## Shared Output Rules

### summary_text
- one compact natural-language summary
- should be readable by the engine and UI
- usually 1 to 3 sentences

### structured_updates
- must contain only fields allowed by the task schema
- must reference only known IDs unless the task allows generating new local IDs

### cacheable_text
- should contain short prose fragments the UI or cache layer can reuse
- do not dump long exposition

### confidence
- 0.0 to 1.0
- reflects output confidence within provided context, not world certainty in the abstract

### warnings
- use for ambiguity, missing context, or partial constraint conflicts
- warnings are preferred over unsupported invention

## Shared Repair Strategy

If output fails validation, the runtime should repair or retry in this order.

1. If JSON is invalid:
   - retry once with a stricter “JSON only” repair prompt
2. If required fields are missing:
   - request a schema-only repair
3. If extra unsupported fields appear:
   - strip unsupported fields if safe, else retry
4. If output scope is too broad:
   - retry with stronger brevity and scope instructions
5. If prose is good but structured fields are weak:
   - keep nothing unless structured output validates

## Token and Size Budget Guidance

These are practical target ranges, not hard provider limits.

- city_seed: larger budget, but still structured-first
- district_expand: medium budget
- location_expand: medium budget
- npc_response: small to medium budget
- clue_update: small budget
- case_fallout: medium budget
- summary_refresh: small budget
- background_precompute: small budget

### MVP rule
Prefer structured density over long prose.
If a task can be answered with 120 useful tokens instead of 500 decorative ones, choose the shorter answer.

## Task 1 — City Seed

## Purpose
Generate a new coherent city instance seed at game start.

## Allowed scope
The task may generate:
- top-level seed fields allowed by `city-seed-schema.md`
- initial district list
- initial faction list
- initial case configuration
- initial NPC anchors
- starting lantern and Missingness configuration

It may not generate:
- scene prose
- full district content details for every future location
- deep case walkthroughs
- full dialogue

## Required input
- task type and request id
- seed parameter set or defaults
- desired city scale for MVP
- required schema version
- design constraints from Lantern City docs

## Required output shape
The structured output must match the city seed schema.
The prose cache should stay short.

### Required cacheable_text fields
- `seed_pitch`
- `city_identity_summary`

## Prompt skeleton

```text
You are generating a new Lantern City seed.
Return valid JSON only.

Goals:
- produce a coherent single-player city instance seed
- preserve Lantern City identity
- create replayable variation without random incoherence
- keep scope appropriate for the MVP

Non-negotiables:
- the engine owns world truth
- output must match the requested schema exactly
- do not add fields outside the schema
- do not write scene prose or long lore essays
- keep the city recognizably Lantern City: noir, wet, civic, memory-strained, lantern-centered

Required design traits:
- lanterns matter politically and socially
- Missingness creates partial absence, contradiction, and denial
- factions have public roles and private agendas
- districts differ in social logic
- the city should feel internally coherent, not random

Return the seed object only.
```

## Validation focus
- all required top-level keys present
- counts match arrays
- IDs are unique and internally consistent
- lantern and Missingness settings fit allowed enums and ranges
- the seed feels like Lantern City, not a generic fantasy city

## Common failure modes
- too much lore, not enough structure
- invented extra keys
- vague district roles
- factions without meaningful tension
- city mood inconsistent with project tone

## Repair hint
If the first output is too verbose, retry with:
- “Return schema-compliant JSON only. No explanations. No markdown. No extra prose.”

## Task 2 — District Expand

## Purpose
Generate a playable district slice when the district is first entered or first needed.

## Allowed scope
The task may generate:
- district summary
- major locations
- local rumor lines
- visible NPC anchors
- local problem framing
- district-specific atmosphere and social texture

It may not generate:
- unrelated district content
- full city lore
- future-case outcomes
- major persistent world changes not already allowed by context

## Required input
- district state object
- city identity summary
- relevant faction footprint
- lantern condition
- Missingness pressure if relevant
- active case linkage if the district matters to a live case

## Required output fields in structured_updates
- `district_summary`
- `major_locations`
- `local_problems`
- `rumor_lines`
- `npc_anchor_ids_or_specs`

## Required cacheable_text fields
- `entry_text`
- `short_summary`

## Prompt skeleton

```text
You are expanding one Lantern City district for active play.
Return valid JSON only.

Task:
Create only the district slice needed for current play.

Rules:
- use the provided district identity and state as truth
- do not alter persistent state outside the allowed output fields
- keep the district socially and mechanically distinct
- make the district feel readable in play, not encyclopedic
- give 3 to 5 useful major locations at most for the MVP slice unless the input explicitly asks for more
- include rumor lines that imply, not solve

Tone:
- restrained
- atmospheric
- civic
- legible
- no purple-prose excess

Do not generate unrelated districts or future scenes.
```

## Validation focus
- district content matches known district role
- locations are useful, not generic filler
- rumors are suggestive and short
- output is compact enough for lazy loading

## Common failure modes
- too many locations
- generic fantasy district flavor
- over-explanation of lantern rules
- NPC anchors with no gameplay role

## Task 3 — Location Expand

## Purpose
Generate one location slice for an active scene or a newly entered location.

## Allowed scope
The task may generate:
- location scene framing
- visible entities
- interactable objects or exits
- immediate investigation hooks
- short local sensory detail

It may not generate:
- deep multi-scene branches
- full district rewrites
- unbounded interactive menus
- unsupported state changes

## Required input
- location state object
- district summary
- local lantern state
- active case context if relevant
- visible NPC list if present

## Required output fields in structured_updates
- `visible_entities`
- `interactable_objects`
- `obvious_exits`
- `scene_hooks`
- `location_tags`

## Required cacheable_text fields
- `location_intro`
- `inspect_text_seed`

## Prompt skeleton

```text
You are expanding one Lantern City location for immediate play.
Return valid JSON only.

Task:
Describe only what the player can immediately perceive and act on.

Rules:
- keep the prose short and scene-usable
- generate 3 to 6 meaningful affordances, not a giant interaction cloud
- reflect lantern state, district tone, and active pressure if relevant
- do not solve the location’s mystery inside the description
- make clues discoverable through action, not through omniscient narration

Output must support a text-first hybrid UI.
```

## Validation focus
- supports actual player action choices
- does not bury the player in decoration
- preserves mystery without vagueness

## Task 4 — NPC Response

## Purpose
Generate one NPC reply inside a bounded scene.

## Allowed scope
The task may generate:
- one reply turn or short conversational block
- one meaningful emotional or social shift
- one refusal, redirect, hint, clue refinement, or concession
- a small set of follow-up action suggestions

It may not generate:
- a full multi-turn conversation tree
- major new facts unsupported by the NPC’s known profile
- resolution of the whole case in a single answer unless the context already supports it

## Required input
- NPC state object
- scene state
- player input or chosen action
- relevant clues
- local lantern condition
- trust, suspicion, fear, loyalty, and hidden-objective summaries

## Required output fields in structured_updates
- `dialogue_act`
- `npc_stance`
- `relationship_shift`
- `clue_effects`
- `access_effects`
- `redirect_targets`

## Required cacheable_text fields
- `npc_line`
- `follow_up_suggestions`
- `exit_line_if_needed`

## Prompt skeleton

```text
You are generating one bounded NPC response in Lantern City.
Return valid JSON only.

Task:
Respond as the provided NPC to the player’s immediate action.

Rules:
- stay within the NPC’s known goals, fears, and knowledge
- the NPC may imply, evade, redirect, or reveal, but should not become omniscient
- produce only one short conversational result, not an entire branch
- if the NPC refuses, the refusal should still be informative or redirective
- if a clue is revealed, it must be consistent with provided clue and world state
- preserve the game’s conversation model: useful quickly, easy to leave, mystery maintained

Tone:
- restrained
- character-specific
- no exposition dump
```

## Validation focus
- voice matches NPC sheet
- response is scene-bounded
- new information fits known NPC slice
- result supports next action options

## Common failure modes
- too much exposition
- NPC says things they should not know
- conversation resolves too much at once
- no meaningful next step

## Repair hint
If response is too broad, retry with:
- “Generate exactly one reply turn plus structured effects. Do not continue the conversation beyond that turn.”

## Task 5 — Clue Update

## Purpose
Create or revise a clue after investigation, comparison, or conversation.

## Allowed scope
The task may generate:
- clue text
- reliability update
- relationship to other clues, people, places, or cases
- contradiction note
- inference note

It may not generate:
- unsupported certainty
- outcome claims beyond the provided evidence state
- rule changes to lantern or Missingness systems

## Required input
- triggering action summary
- relevant evidence sources
- lantern condition and Missingness state
- any existing clue object if updating rather than creating
- relevant linked entities

## Required output fields in structured_updates
- `clue_id_or_temp_key`
- `clue_text`
- `source_type`
- `reliability`
- `related_ids`
- `contradiction_note`
- `inference_note`

## Required cacheable_text fields
- `journal_entry`
- `short_clue_label`

## Prompt skeleton

```text
You are generating or updating one Lantern City clue.
Return valid JSON only.

Task:
Produce a clue object or clue revision based only on the supplied evidence context.

Rules:
- clue reliability must reflect source type, lantern state, and Missingness rules
- use the allowed reliability labels only
- distinguish direct evidence from inference
- if the clue is unstable, contradicted, or distorted, say so explicitly in the structured fields
- do not claim proof if only suggestive evidence exists
- keep clue text concise and game-usable

This task is about evidence quality, not dramatic prose.
```

## Validation focus
- reliability label fits clue source and world state
- linked IDs are valid
- clue text is concise and useful
- contradiction and inference are not conflated

## Common failure modes
- clue text too literary
- confidence overstated
- contradiction treated as certainty

## Task 6 — Case Fallout

## Purpose
Generate the local aftermath of a major case shift or resolution.

## Allowed scope
The task may generate:
- immediate district consequences
- faction posture reactions
- NPC memory or attitude summaries
- follow-up hooks
- public mood change summaries

It may not generate:
- a whole new campaign arc
- unrelated citywide upheaval unless explicitly authorized by state
- unsupported permanent changes

## Required input
- case state before and after the trigger
- district state
- involved factions
- involved major NPCs
- chosen resolution path
- relevant progression changes

## Required output fields in structured_updates
- `case_status_change`
- `district_consequences`
- `faction_reactions`
- `npc_memory_updates`
- `follow_up_hooks`
- `public_mood_shift`

## Required cacheable_text fields
- `fallout_summary`
- `district_notice_text`
- `case_board_resolution_text`

## Prompt skeleton

```text
You are generating Lantern City case fallout.
Return valid JSON only.

Task:
Describe the immediate consequences of a case shift or resolution.

Rules:
- fallout must follow from the provided resolution path and world state
- consequences should be local and specific before they are broad and dramatic
- preserve faction nuance; do not flatten every reaction into simple approval or anger
- show what changed in the district, institutions, and relationships
- include hooks for future play only if they grow naturally from the current case
- do not invent unrelated crises

Fallout should make the city feel persistent.
```

## Validation focus
- consequences match the actual resolution path
- factions react according to dossier logic
- fallout is persistent but bounded
- future hooks are plausible, not sequel bait noise

## Task 7 — Summary Refresh

## Purpose
Refresh a cached short summary when state has changed enough to invalidate it.

## Allowed scope
The task may generate:
- one short district summary
- one short location summary
- one short NPC summary
- one short case-board summary

It may not generate:
- new facts
- new content objects
- deep narrative scenes

## Required input
- the target object
- the target object’s current state
- the prior cached summary if available
- reason for refresh

## Required output fields in structured_updates
- `target_id`
- `summary_type`
- `summary_version_note`

## Required cacheable_text fields
- `short_summary`
- `long_summary_if_requested`

## Prompt skeleton

```text
You are refreshing a cached Lantern City summary.
Return valid JSON only.

Task:
Rewrite the summary so it matches current state.

Rules:
- summarize only what is now true in the provided state
- do not invent new facts
- keep summaries compact and reusable
- preserve tone, but favor clarity over flourish
- if little changed, reflect the small change instead of rewriting dramatically
```

## Validation focus
- summary matches current state
- no new facts introduced
- compact enough for cache use

## Task 8 — Background Precompute

## Purpose
Precompute one likely next-step content packet for latency reduction.

## Allowed scope
The task may generate:
- one likely next NPC response seed
- one likely transition scene seed
- one likely location intro seed
- one likely clue clarification seed

It may not generate:
- multiple future branches
- speculative major world updates
- deep content the player has not meaningfully approached

## Required input
- current scene state
- current action options
- likely-next-step heuristic
- relevant local state slice

## Required output fields in structured_updates
- `precompute_type`
- `target_context`
- `invalidates_when`

## Required cacheable_text fields
- one narrow text seed appropriate to the precompute type

## Prompt skeleton

```text
You are generating one likely next-step precompute for Lantern City.
Return valid JSON only.

Task:
Produce only one narrow likely-next-step content seed.

Rules:
- optimize for reuse, not completeness
- do not assume the player must choose this branch
- keep the seed easy to discard if state changes
- no major new facts or irreversible consequences
```

## Validation focus
- only one branch precomputed
- easy invalidation conditions
- no speculative overreach

## What Must Never Be Invented Without Explicit Authorization

Across all tasks, the model must not invent any of the following unless the task explicitly requests them.

- new districts
- new major factions
- new persistent NPCs beyond a local anchor request
- new hidden rules of lanterns or Missingness
- new progression tracks
- irreversible district-level catastrophe
- case resolution without state support
- broad city history changes

## Tone and Style Guardrails by Task

### Seed, district, and location tasks
- concise and atmospheric
- civic detail over fantasy flourish
- strong nouns, restrained adjectives

### NPC response tasks
- character-specific
- implication-heavy
- short enough for play rhythm

### Clue tasks
- precise and compact
- minimal ornament
- evidence-first wording

### Fallout and summary tasks
- clear consequence language
- emotionally restrained
- avoid melodrama

## Example Negative Instructions

These should appear where relevant.

- Do not narrate outcomes the engine has not authorized.
- Do not resolve unanswered questions unless the provided evidence supports resolution.
- Do not create poetic ambiguity where the task needs operational clarity.
- Do not return markdown.
- Do not include commentary outside the JSON object.

## Model Selection Guidance

For the MVP, smaller and cheaper models may be acceptable for:
- summary_refresh
- clue_update
- background_precompute

Stronger models may be preferable for:
- city_seed
- district_expand
- npc_response when social nuance matters
- case_fallout when multiple faction reactions must stay coherent

## Runtime Integration Notes

The orchestrator should attach only the context needed for the task.
The prompt builder should not simply dump raw documents.
It should compile:
- task instruction
- world-rule reminder
- compact object slice
- schema definition
- explicit forbidden moves

This is critical.
The contract only works if the input context is narrow and curated.

## Design Rules

1. Every task must stay narrow.
2. Structured output matters more than decorative prose.
3. The engine decides truth; the model expresses it locally.
4. Warnings are better than unsupported invention.
5. Repair should be schema-first and cheap.
6. Prompt contracts should preserve Lantern City tone without sacrificing clarity.
7. No task should generate more future than the current request actually needs.

## Summary

These prompt contracts close the gap between Lantern City’s design and its generation architecture.
They define how each generation task should behave, what it may produce, what it must never produce, and how the runtime should validate and repair the result.

If followed, they should make the LLM layer usable as a constrained content engine rather than a freeform world-author.