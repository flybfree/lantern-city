# Lantern City — Coding Agent Tasklist

> **Use this tasklist to implement the Lantern City MVP.**
> The goal is to build the backend foundations first, then the lazy-generation game loop, then a minimal playable shell.

## Recommended Tech Stack

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

## Packaging and Tooling Assumptions

Use the following `pyproject.toml` approach:
- Hatchling as the build backend
- `src/` layout
- `lantern_city.cli:main` as the console script entry point
- pytest configured with `tests/` as test root and `src/` on the Python path
- ruff for linting and formatting

The repo should be initialized with a `pyproject.toml` matching these assumptions before code implementation begins.

## Project Structure

Use this repository layout:

```text
lantern-city/
├── pyproject.toml
├── README.md
├── src/
│   └── lantern_city/
│       ├── __init__.py
│       ├── app.py
│       ├── cli.py
│       ├── models.py
│       ├── serialization.py
│       ├── store.py
│       ├── seed_schema.py
│       ├── orchestrator.py
│       ├── active_slice.py
│       ├── engine.py
│       ├── response.py
│       ├── cache.py
│       ├── background.py
│       ├── progression.py
│       ├── cases.py
│       ├── clues.py
│       ├── lanterns.py
│       ├── llm_client.py
│       ├── bootstrap.py
│       └── generation/
│           ├── __init__.py
│           ├── city_seed.py
│           ├── district.py
│           ├── npc_response.py
│           └── fallout.py
└── tests/
    ├── test_models.py
    ├── test_serialization.py
    ├── test_store.py
    ├── test_seed_schema.py
    ├── test_city_seed_generation.py
    ├── test_bootstrap.py
    ├── test_orchestrator.py
    ├── test_active_slice.py
    ├── test_engine.py
    ├── test_llm_client.py
    ├── test_district_generation.py
    ├── test_npc_response.py
    ├── test_clues.py
    ├── test_lanterns.py
    ├── test_progression.py
    ├── test_cases.py
    ├── test_fallout.py
    ├── test_cache.py
    ├── test_background.py
    ├── test_cli.py
    └── test_end_to_end.py
```

## Scope Reminder

MVP goals:
- one seeded persistent city instance per run
- SQLite-backed storage
- narrow LLM calls only for relevant interactions
- lazy generation by city / district / scene / NPC response
- persistent cases, clues, progression, and lantern state
- a minimal playable loop proving the city reacts to player choices

## Execution Rules for the Coding Agent

- Work task-by-task in order.
- Use TDD where practical.
- Keep each task small and reviewable.
- Do not build extra features beyond the MVP.
- Preserve the separation between persistent state and generated text.
- Keep LLM prompts narrow and structured.

---

## Phase 1: Project Skeleton and Storage

### Task 1: Create the Lantern City project package

**Objective:** Create the base package structure and entry points.

**Files to create:**
- `src/lantern_city/__init__.py`
- `src/lantern_city/models.py`
- `src/lantern_city/store.py`
- `src/lantern_city/serialization.py`
- `tests/test_models.py`
- `tests/test_serialization.py`
- `tests/test_store.py`

**Deliverable:**
A Python package that can define and persist the core world-state objects.

---

### Task 2: Implement the core world-state models

**Objective:** Define all persistent and transient runtime objects.

**Files to create/modify:**
- `src/lantern_city/models.py`
- `tests/test_models.py`

**Models required:**
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

**Deliverable:**
Validated structured objects with stable IDs, versioning, timestamps, and JSON-friendly fields.

---

### Task 3: Add JSON serialization helpers

**Objective:** Round-trip model objects cleanly to/from JSON.

**Files to create/modify:**
- `src/lantern_city/serialization.py`
- `tests/test_serialization.py`

**Deliverable:**
Helpers that can serialize any model to JSON and restore it without losing fields.

---

### Task 4: Build SQLite-backed world storage

**Objective:** Persist world objects and caches in SQLite.

**Files to create/modify:**
- `src/lantern_city/store.py`
- `tests/test_store.py`

**Storage requirements:**
- generic `world_objects` table for persistent state
- generic `cache_entries` table for generated summaries/text
- load/save/list/update operations
- version-based cache invalidation support

**Deliverable:**
A simple store interface that saves and loads all runtime objects.

---

## Phase 2: Seed Schema and City Bootstrapping

### Task 5: Implement city seed validation

**Objective:** Validate seed JSON against the schema before bootstrapping a city.

**Files to create/modify:**
- `src/lantern_city/seed_schema.py`
- `tests/test_seed_schema.py`

**Deliverable:**
Validation that rejects malformed seed data and accepts the documented schema.

---

### Task 6: Implement city seed generation interface

**Objective:** Create a task-specific generator interface for city seeds.

**Files to create/modify:**
- `src/lantern_city/llm_client.py`
- `src/lantern_city/generation/city_seed.py`
- `tests/test_city_seed_generation.py`

**Deliverable:**
A provider-agnostic method that requests a structured city seed JSON object.

---

### Task 7: Build city bootstrap from seed

**Objective:** Convert a validated seed into a persistent city instance.

**Files to create/modify:**
- `src/lantern_city/bootstrap.py`
- `tests/test_bootstrap.py`

**Deliverable:**
Bootstrap logic that writes CityState, DistrictState, FactionState, LanternState, CaseState, NPCState, and PlayerProgressState into storage.

---

## Phase 3: Request Lifecycle and Active Slice

### Task 8: Implement request classification and orchestration

**Objective:** Route player actions to the correct backend flow.

**Files to create/modify:**
- `src/lantern_city/orchestrator.py`
- `tests/test_orchestrator.py`

**Intents to support:**
- district entry
- talk to NPC
- inspect location
- case progression
- generic action

**Deliverable:**
A small orchestrator that determines what state must be loaded for each action.

---

### Task 9: Implement the active working set builder

**Objective:** Keep the current city slice small and explicit.

**Files to create/modify:**
- `src/lantern_city/active_slice.py`
- `tests/test_active_slice.py`

**Deliverable:**
A builder that gathers only the current district, location, scene, NPCs, clues, and case.

---

### Task 10: Implement the request lifecycle handler

**Objective:** Turn one player request into state updates and a player-facing response.

**Files to create/modify:**
- `src/lantern_city/engine.py`
- `tests/test_engine.py`

**Deliverable:**
A single function that loads relevant state, generates narrow output if needed, applies rules, persists changes, and returns a response object.
Responses must make meaningful outcomes legible, including introducing pre-case clues as noteworthy even when their meaning is still unclear.

---

## Phase 4: Generation Layer

### Task 11: Implement LLM client with provider abstraction

**Objective:** Support OpenAI-compatible and local-compatible backends behind one interface.

**Files to create/modify:**
- `src/lantern_city/llm_client.py`
- `tests/test_llm_client.py`

**Deliverable:**
A task-based generation client with methods for city seed, district expansion, NPC response, clue update, fallout, and background precompute.

---

### Task 12: Implement district expansion generation

**Objective:** Lazily generate district details on first entry.

**Files to create/modify:**
- `src/lantern_city/generation/district.py`
- `tests/test_district_generation.py`

**Deliverable:**
Structured district summary, local locations, rumor pool, and nearby NPC anchors.

---

### Task 13: Implement NPC response generation

**Objective:** Generate narrow, context-specific NPC conversation branches.

**Files to create/modify:**
- `src/lantern_city/generation/npc_response.py`
- `tests/test_npc_response.py`

**Deliverable:**
Dialogue text plus structured updates such as clue changes, relationship deltas, and next actions.
If an NPC surfaces a clue tied to a case the player has not formally discovered yet, the response should flag it as unusual, relevant, or worth remembering without explaining the whole case too early.

---

### Task 14: Implement clue generation and updates

**Objective:** Track clue creation, clarification, contradiction, and status changes.

**Files to create/modify:**
- `src/lantern_city/clues.py`
- `tests/test_clues.py`

**Deliverable:**
A clue lifecycle with reliability and status management.
This includes pre-case clue discovery, with enough signaling metadata or rule support for the response layer to present the clue as significant before the case is active.

---

### Task 15: Implement lantern state effects

**Objective:** Make lantern condition changes affect access, memory, and clue reliability.

**Files to create/modify:**
- `src/lantern_city/lanterns.py`
- `tests/test_lanterns.py`

**Deliverable:**
Rules for bright / dim / flickering / extinguished / altered lantern states.

---

## Phase 5: Progression and Case Logic

### Task 16: Implement progression tracks

**Objective:** Track Lantern Understanding, Access, Reputation, Leverage, City Impact, and Clue Mastery.

**Files to create/modify:**
- `src/lantern_city/progression.py`
- `tests/test_progression.py`

**Deliverable:**
Tier-based progression updates with thresholds.

---

### Task 17: Implement case state transitions

**Objective:** Track active, stalled, escalated, solved, partially solved, and failed cases.

**Files to create/modify:**
- `src/lantern_city/cases.py`
- `tests/test_cases.py`

**Deliverable:**
A case engine that reacts to clue discovery and player actions.

---

### Task 18: Implement fallout generation

**Objective:** Generate localized consequences after meaningful choices.

**Files to create/modify:**
- `src/lantern_city/generation/fallout.py`
- `tests/test_fallout.py`

**Deliverable:**
A narrow fallout generator that updates nearby state and case conditions.

---

## Phase 6: Caching and Efficiency

### Task 19: Implement cache invalidation rules

**Objective:** Keep generated summaries coherent when source state changes.

**Files to create/modify:**
- `src/lantern_city/cache.py`
- `tests/test_cache.py`

**Deliverable:**
Cache entries that invalidate when related objects version-change.

---

### Task 20: Implement background precomputation

**Objective:** Precompute one likely next step without generating too far ahead.

**Files to create/modify:**
- `src/lantern_city/background.py`
- `tests/test_background.py`

**Deliverable:**
A lightweight precompute job for the next likely district, scene, or NPC response.

---

## Phase 7: Minimal Playable Interface

### Task 21: Add a minimal CLI or web shell

**Objective:** Provide a simple way to start a city and issue requests.

**Files to create/modify:**
- `src/lantern_city/cli.py` or `src/lantern_city/app.py`
- `tests/test_cli.py`

**Deliverable:**
A basic playable shell that proves the end-to-end loop works.

---

### Task 22: Add end-to-end tests

**Objective:** Prove the MVP flow from seed to case progression.

**Files to create/modify:**
- `tests/test_end_to_end.py`

**Scenarios to test:**
- new city generation
- district entry
- NPC conversation
- clue update
- lantern state change
- case progression
- cache reuse

**Deliverable:**
A passing test suite that demonstrates the main gameplay loop.

---

## Phase 8: Documentation and Cleanup

### Task 23: Document the backend contract

**Objective:** Keep the implementation aligned with the design docs.

**Files to modify:**
- `backend/storage-spec.md`
- `backend/llm-interface-spec.md`
- `backend/state-orchestration.md`
- `backend/api-contract.md`

**Deliverable:**
Any implementation-specific changes reflected in the docs.

---

### Task 24: Final review and cleanup

**Objective:** Remove dead code, ensure all models and flows are consistent, and prepare for the next phase.

**Files:**
- all implementation files touched above

**Deliverable:**
A coherent MVP backend ready for the first full playthrough.

---

## Build Order Recommendation

Recommended implementation order:
1. Models and serialization
2. SQLite storage
3. Seed validation
4. Seed generation
5. Bootstrap
6. Orchestrator and active slice
7. LLM client and generation tasks
8. Clue / lantern / progression / case rules
9. Cache invalidation and background precompute
10. CLI shell and end-to-end tests

---

## Definition of Done

The Lantern City MVP backend is ready when:
- a valid city seed can initialize a persistent city
- player requests load only relevant state
- generation stays narrow and cached
- lanterns affect play meaningfully
- cases and clues persist
- progression advances
- the city can be restarted into a fresh, distinct run
