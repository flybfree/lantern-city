# Lantern City — Subagent Execution Plan

> Use this plan to execute the Lantern City MVP with fresh subagents per task.
> Follow the two-stage review process for every task:
> 1. Spec compliance review
> 2. Code quality review

## Operating Rules

- Use one implementation subagent per task.
- Do not assign two subagents to edit the same files at the same time.
- Keep tasks sequential unless they are clearly independent.
- Provide the subagent with all needed context in the task prompt.
- The subagent should not need to read the whole plan file.
- After implementation, run spec review, then quality review.
- Do not proceed to the next task until both reviews pass.

## Project Assumptions

- Python 3.12
- FastAPI
- SQLite
- SQLAlchemy 2.x
- Pydantic v2
- httpx
- pytest
- ruff
- uv
- Hatchling build backend
- `src/` layout
- console script entry point: `lantern_city.cli:main`

## Repository State Expected Before Execution

- Git repository initialized
- `pyproject.toml` in place
- `.gitignore` in place
- docs baseline committed
- virtual environment available

## Architectural Note

This plan was originally written around the MVP vertical slice.
The runtime has since evolved toward a deeper simulation model.

Treat these as two separate layers:

- `MVP baseline loop`
  The short, deterministic authored path that proves the game works end to end.
  This is the loop used for onboarding, core regression tests, and first-play validation.

- `Evolved runtime`
  The broader simulation layer with latent cases, offscreen pressure, deeper clue interpretation, and stronger social/systemic state changes.

Execution rule:
- do not let MVP shortcut assumptions silently define the general runtime
- do not let newer simulation rules accidentally break the authored MVP proof-of-loop path
- if a task touches shared logic, explicitly decide whether it belongs to MVP baseline behavior, evolved runtime behavior, or both

## Task Grouping Strategy

This plan is arranged to reduce file contention and keep progress safe:

1. Data model and serialization
2. Storage and seed validation
3. Bootstrap and orchestration
4. Generation interface and narrow generators
5. Game rules and progression
6. Caching and background precompute
7. Minimal CLI and end-to-end verification

---

## Task 1: Core Models

**Goal for implementer subagent:**
Create the core world-state models and make them testable.

**Files to create:**
- `src/lantern_city/models.py`
- `tests/test_models.py`

**Context to provide:**
- The game uses persistent JSON-friendly state objects.
- Required models:
  - CitySeed
  - CityState
  - DistrictState
  - LocationState
  - NPCState
  - FactionState
  - LanternState
  - CaseState
  - SceneState
  - ClueState
  - PlayerProgressState
  - PlayerRequest
  - GenerationJob
  - GeneratedOutput
  - PlayerResponse
  - ActiveWorkingSet
- Every model should have stable IDs, type labels, versioning, created_at, updated_at.
- Use Pydantic v2 or a similar structured model approach.
- Keep fields JSON-serializable.

**Implementation guidance:**
- Start with failing tests.
- Add minimal models to make tests pass.
- Avoid overengineering relationships; references by ID are enough.

**Verification:**
- `pytest tests/test_models.py -v`
- full test suite should remain green after implementation

**Review process:**
1. Spec review: Are all required models present and shaped correctly?
2. Quality review: Are names clear, models consistent, and fields sensible?

---

## Task 2: Serialization Helpers

**Goal for implementer subagent:**
Add JSON serialization and round-trip helpers for the models.

**Files to create:**
- `src/lantern_city/serialization.py`
- `tests/test_serialization.py`

**Context to provide:**
- Models must serialize cleanly to JSON.
- The runtime will store and load objects from SQLite as JSON payloads.
- Round-tripping should preserve fields and types.

**Implementation guidance:**
- Use simple, explicit JSON conversion.
- Keep helper functions generic enough for all model classes.

**Verification:**
- `pytest tests/test_serialization.py -v`
- ensure model round-trip passes

**Review process:**
1. Spec review: Does serialization preserve the required shape?
2. Quality review: Is the code straightforward and reusable?

---

## Task 3: SQLite Storage Layer

**Goal for implementer subagent:**
Create persistent storage for world objects and caches.

**Files to create:**
- `src/lantern_city/store.py`
- `tests/test_store.py`

**Context to provide:**
- SQLite is the durable store for the single-player MVP.
- Store two logical groups:
  - persistent world objects
  - cache entries
- Recommended generic tables:
  - `world_objects`
  - `cache_entries`
- Store should support save, load, list, and invalidation behavior.

**Implementation guidance:**
- Keep storage boring and reliable.
- Use versioning in persistence records.
- Preserve object IDs and types.

**Verification:**
- `pytest tests/test_store.py -v`
- verify save/load round-trips

**Review process:**
1. Spec review: Does the store satisfy the documented persistence strategy?
2. Quality review: Are the methods clear, testable, and not overcomplicated?

---

## Task 4: Seed Schema Validation

**Goal for implementer subagent:**
Validate city seed JSON before bootstrapping a run.

**Files to create:**
- `src/lantern_city/seed_schema.py`
- `tests/test_seed_schema.py`

**Context to provide:**
- The city seed has top-level sections:
  - city_identity
  - district_configuration
  - faction_configuration
  - lantern_configuration
  - missingness_configuration
  - case_configuration
  - npc_configuration
  - progression_start_state
  - tone_and_difficulty
- Validation should reject malformed or incomplete seeds.
- Validation should accept the documented schema.

**Implementation guidance:**
- Use Pydantic models or a focused validator layer.
- Keep validation strict enough to catch bad seeds early.

**Verification:**
- `pytest tests/test_seed_schema.py -v`

**Review process:**
1. Spec review: Does the validator enforce the documented required structure?
2. Quality review: Are error messages clear and maintainable?

---

## Task 5: LLM Client Abstraction and City Seed Generation

**Goal for implementer subagent:**
Build a provider-agnostic LLM client and city seed generation flow.

**Files to create:**
- `src/lantern_city/llm_client.py`
- `src/lantern_city/generation/city_seed.py`
- `tests/test_llm_client.py`
- `tests/test_city_seed_generation.py`

**Context to provide:**
- The LLM only receives narrow context for one task at a time.
- Client must support OpenAI-compatible backends.
- City seed generation must return structured JSON matching the schema.
- The engine owns world state; the model only generates content.

**Implementation guidance:**
- Make task-based methods for city seed generation.
- Validate outputs before use.
- Start with one provider abstraction path.

**Verification:**
- `pytest tests/test_llm_client.py -v`
- `pytest tests/test_city_seed_generation.py -v`

**Review process:**
1. Spec review: Does the client honor the narrow, structured generation contract?
2. Quality review: Is provider abstraction clean and future-proof without overbuilding?

---

## Task 6: City Bootstrap

**Goal for implementer subagent:**
Convert a validated city seed into persistent world state.

**Files to create:**
- `src/lantern_city/bootstrap.py`
- `tests/test_bootstrap.py`

**Context to provide:**
- Bootstrap must create and persist:
  - CityState
  - DistrictState
  - FactionState
  - LanternState
  - CaseState
  - NPCState
  - PlayerProgressState
- This task should use the seed schema and store layer.

**Implementation guidance:**
- Keep bootstrap deterministic relative to the seed.
- Use the seed as the source of truth for the initial world shape.

**Verification:**
- `pytest tests/test_bootstrap.py -v`

**Review process:**
1. Spec review: Are the correct world objects created and persisted?
2. Quality review: Is the bootstrap logic simple and consistent with the data model?

---

## Task 7: Request Orchestration and Active Slice

**Goal for implementer subagent:**
Route player requests and load only the relevant slice of state.

**Files to create:**
- `src/lantern_city/orchestrator.py`
- `src/lantern_city/active_slice.py`
- `tests/test_orchestrator.py`
- `tests/test_active_slice.py`

**Context to provide:**
- Supported intents:
  - district entry
  - talk to NPC
  - inspect location
  - case progression
  - generic action
- The active slice should contain only the current district, location, scene, NPCs, clues, and case.

**Implementation guidance:**
- Keep intent classification simple and explicit.
- The active slice should be small enough to support narrow generation.

**Verification:**
- `pytest tests/test_orchestrator.py -v`
- `pytest tests/test_active_slice.py -v`

**Review process:**
1. Spec review: Does the orchestrator load only what is needed?
2. Quality review: Are the classification rules and slice builder clean and maintainable?

---

## Task 8: Request Lifecycle Engine

**Goal for implementer subagent:**
Turn a player request into state updates and a response.

**Files to create:**
- `src/lantern_city/engine.py`
- `src/lantern_city/response.py`
- `tests/test_engine.py`
- `tests/test_response.py`

**Context to provide:**
- The engine should load relevant state, generate narrow output if needed, apply rules, persist changes, and return a response.
- Response should include narrative text, state changes, and next actions.
- If the player encounters a clue before the related case is active, the response must frame it as noteworthy so the player knows it matters even if its meaning is still unclear.
- The player should not need to guess whether a scene produced something meaningful; responses should surface that legibly after the fact.

**Implementation guidance:**
- Keep request handling narrow and deterministic where possible.
- Use the state engine for authoritative updates.

**Verification:**
- `pytest tests/test_engine.py -v`
- `pytest tests/test_response.py -v`

**Review process:**
1. Spec review: Does the request lifecycle match the documented flow?
2. Quality review: Is the response layer simple, clear, and reusable?

---

## Task 9: District and NPC Generation

**Goal for implementer subagent:**
Add narrow generation for districts and NPC dialogue.

**Files to create:**
- `src/lantern_city/generation/district.py`
- `src/lantern_city/generation/npc_response.py`
- `tests/test_district_generation.py`
- `tests/test_npc_response.py`

**Context to provide:**
- District generation should create a district summary, nearby locations, rumor pool, and relevant NPC anchors.
- NPC generation should produce dialogue plus structured updates like clue changes and relationship deltas.
- If NPC dialogue surfaces a clue tied to a case the player has not formally discovered yet, the GM-style presentation should mark it as unusual, relevant, or worth remembering without prematurely explaining the case.

**Implementation guidance:**
- Keep generation tightly scoped to the current context packet.
- Ensure outputs are structured and validated.

**Verification:**
- `pytest tests/test_district_generation.py -v`
- `pytest tests/test_npc_response.py -v`

**Review process:**
1. Spec review: Do generated outputs match the expected task contracts?
2. Quality review: Are the generators narrow, testable, and not over-coupled?

---

## Task 10: Clues, Lanterns, Progression, and Cases

**Goal for implementer subagent:**
Implement the core rule systems that make Lantern City react.

**Files to create:**
- `src/lantern_city/clues.py`
- `src/lantern_city/lanterns.py`
- `src/lantern_city/progression.py`
- `src/lantern_city/cases.py`
- `tests/test_clues.py`
- `tests/test_lanterns.py`
- `tests/test_progression.py`
- `tests/test_cases.py`

**Context to provide:**
- Clues should support creation, clarification, contradiction, and status changes.
- Lantern states should affect access, memory, and clue reliability.
- Progression tracks:
  - Lantern Understanding
  - Access
  - Reputation
  - Leverage
  - City Impact
  - Clue Mastery
- Cases should support active, stalled, escalated, solved, partially solved, and failed.
- Pre-case clue discovery must be supported. A clue can exist before its case is active, but the system should attach enough presentation metadata or signaling rules for the response layer to introduce it as significant even when its meaning is not yet known.

**Implementation guidance:**
- Keep rules explicit and understandable.
- Use the documented thresholds and tiers.

**Verification:**
- run each focused test file individually
- then run the full suite

**Review process:**
1. Spec review: Do the rule systems reflect the design docs?
2. Quality review: Are the modules cleanly separated and easy to reason about?

---

## Task 11: Cache and Background Precompute

**Goal for implementer subagent:**
Keep generation efficient through cache invalidation and small background precompute.

**Files to create:**
- `src/lantern_city/cache.py`
- `src/lantern_city/background.py`
- `tests/test_cache.py`
- `tests/test_background.py`

**Context to provide:**
- Cache entries should invalidate when source object versions change.
- Background generation should only prepare one likely next step.

**Implementation guidance:**
- Avoid broad pre-generation.
- Keep cache keys and invalidation logic explicit.

**Verification:**
- `pytest tests/test_cache.py -v`
- `pytest tests/test_background.py -v`

**Review process:**
1. Spec review: Does the cache behavior match the lazy-generation design?
2. Quality review: Is the caching layer simple and low-risk?

---

## Task 12: Minimal CLI and End-to-End Validation

**Goal for implementer subagent:**
Provide a minimal playable shell and end-to-end tests.

**Files to create:**
- `src/lantern_city/cli.py`
- `src/lantern_city/app.py` if needed
- `tests/test_cli.py`
- `tests/test_end_to_end.py`

**Context to provide:**
- The MVP only needs a minimal interface to prove the loop works.
- End-to-end flow should cover seed -> district -> NPC -> clue -> lantern/state -> case progression.

**Implementation guidance:**
- Keep the shell simple.
- Focus on proving the backend works end to end.

**Verification:**
- `pytest tests/test_cli.py -v`
- `pytest tests/test_end_to_end.py -v`
- then `pytest tests/ -q`

**Review process:**
1. Spec review: Does the shell prove the intended MVP loop?
2. Quality review: Is the interface minimal and not overbuilt?

---

## Final Integration Review

After all tasks pass:
- run the full test suite
- review the implementation for consistency
- verify docs still match behavior
- prepare the first integration commit or release checkpoint

## Suggested Final Checks

- `pytest tests/ -q`
- `ruff check src tests`
- `ruff format --check src tests`
- inspect `git diff --stat`

## Ready-to-Use Subagent Pattern

For each task, use this template:

```text
Goal: [task goal]
Context: [task-specific context]
Toolsets: terminal, file
Max iterations: 15

Implement the task with TDD where practical.
After implementation, verify the spec checklist.
Then verify code quality.
Do not proceed until both reviewers approve.
```

## Final Rule

Fresh subagent per task.
Spec review first.
Quality review second.
No skipping.

---

## Post-MVP Next Execution Slice

Once the current MVP/runtime cleanup is stable, the next systemic implementation slice should follow:

- `briefs/world-turn-and-social-simulation-brief.md`

That slice should be treated as the next major evolved-runtime phase, not as incidental polish.

### Recommended order for that phase

1. world turn engine and idle-delay catch-up
2. social-state expansion for NPC memory and relationships
3. faction pressure and operation rules
4. case evolution tied to actor pressure and elapsed turns
5. TUI/response surfacing for time passage and offscreen changes

### First coding target

The safest first implementation target is:

- `src/lantern_city/simulation.py`
- `src/lantern_city/app.py`
- `tests/test_simulation.py`

Goal:

- define one deterministic world-turn advancement pipeline
- advance one turn per meaningful player action
- support bounded catch-up turns after player delay
- surface readable notices about what changed

### Boundary rule

This phase belongs primarily to the `evolved_runtime`.
If shared logic touches `mvp_baseline`, keep any reduced or bypassed baseline behavior explicit rather than letting the deeper simulation become the accidental default for the authored onboarding path.
