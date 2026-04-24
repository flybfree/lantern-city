# Lantern City Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build the smallest playable Lantern City MVP with a seeded persistent city, lazy generation, progression tracks, NPC interactions, and one case-driven investigative loop.

**Architecture:**
Use a persistent world-state model backed by cached JSON objects. Generate the city in layers: seed -> district -> location/scene -> NPC response -> fallout. Keep only the active slice of the city in memory while storing all other state durably. The runtime should be able to load a narrow context, generate only missing detail, apply rule-based state changes, and persist updates after every meaningful action.
Meaningful outcomes must be legible in the response layer; if the player encounters a clue before the related case is formally active, the game should still frame it as significant even if its meaning is unclear.

**Tech Stack:**
- Python backend
- JSON files or SQLite for persistence
- LLM API for generation
- Optional minimal CLI or web UI for interaction
- Test framework: pytest

---

## Implementation Strategy

Build in the following order:
1. Data model and storage
2. Seed generation and world initialization
3. State loading and request lifecycle
4. District entry generation
5. NPC interaction generation
6. Clue and progression updates
7. Case advancement and closure
8. Lazy background generation and caching
9. Minimal player-facing interface
10. Tests and verification

---

## Phase 1: Core Data Model and Storage

### Task 1: Create the persistent world-state schema

**Objective:** Define the core runtime objects used by the game.

**Files:**
- Create: `src/lantern_city/models.py`
- Create: `tests/test_models.py`

**Required objects:**
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

**Step 1: Write failing test**

```python
from lantern_city.models import CityState


def test_city_state_has_required_fields():
    city = CityState(id="city_001", type="CityState", version=1)
    assert city.id == "city_001"
    assert city.type == "CityState"
    assert city.version == 1
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — model module or class does not exist yet

**Step 3: Write minimal implementation**

Implement the data objects as dataclasses or pydantic models with the required fields.

**Step 4: Run test to verify pass**

Run: `pytest tests/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/models.py tests/test_models.py
git commit -m "feat: add core world-state models"
```

---

### Task 2: Add serialization helpers for the models

**Objective:** Make the world-state objects saveable and loadable as JSON.

**Files:**
- Create: `src/lantern_city/serialization.py`
- Modify: `src/lantern_city/models.py`
- Create: `tests/test_serialization.py`

**Step 1: Write failing test**

```python
from lantern_city.models import CityState
from lantern_city.serialization import to_json, from_json


def test_round_trip_city_state():
    city = CityState(id="city_001", type="CityState", version=1)
    data = to_json(city)
    restored = from_json(CityState, data)
    assert restored.id == city.id
    assert restored.type == city.type
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_serialization.py -v`
Expected: FAIL — serialization helpers missing

**Step 3: Write minimal implementation**

Add JSON conversion helpers that use the model’s dict/export methods.

**Step 4: Run test to verify pass**

Run: `pytest tests/test_serialization.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/serialization.py src/lantern_city/models.py tests/test_serialization.py
git commit -m "feat: add JSON serialization helpers"
```

---

### Task 3: Create the persistent store interface

**Objective:** Add a storage abstraction for saving and loading world-state objects.

**Files:**
- Create: `src/lantern_city/store.py`
- Create: `tests/test_store.py`

**Step 1: Write failing test**

```python
from lantern_city.store import WorldStore


def test_store_can_save_and_load_city_state(tmp_path):
    store = WorldStore(tmp_path)
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL — store does not exist

**Step 3: Write minimal implementation**

Implement a file-based store or SQLite-backed store with methods:
- save(object)
- load(type, id)
- list_ids(type)

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/store.py tests/test_store.py
git commit -m "feat: add persistent world store"
```

---

## Phase 2: Seed Generation and Initialization

### Task 4: Implement city seed generation

**Objective:** Generate a coherent starting city instance.

**Files:**
- Create: `src/lantern_city/generation/city_seed.py`
- Create: `tests/test_city_seed.py`

**Step 1: Write failing test**

```python
from lantern_city.generation.city_seed import generate_city_seed


def test_city_seed_returns_required_fields():
    seed = generate_city_seed()
    assert seed.city_premise
    assert len(seed.district_ids) >= 2
    assert len(seed.faction_ids) >= 2
```

**Step 2: Run test to verify failure**

Expected: FAIL — generator missing

**Step 3: Write minimal implementation**

Generate a structured seed with at least 2 districts, 2 factions, one case, and key NPC anchors.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/generation/city_seed.py tests/test_city_seed.py
git commit -m "feat: add city seed generation"
```

---

### Task 5: Create a city initialization routine

**Objective:** Convert a city seed into a persistent world instance.

**Files:**
- Create: `src/lantern_city/bootstrap.py`
- Create: `tests/test_bootstrap.py`

**Step 1: Write failing test**

```python
from lantern_city.bootstrap import initialize_city


def test_initialize_city_persists_seed_and_state(tmp_path):
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL — bootstrap missing

**Step 3: Write minimal implementation**

Create CityState, DistrictState, FactionState, NPC anchors, and opening CaseState from the seed and store them.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/bootstrap.py tests/test_bootstrap.py
git commit -m "feat: initialize persistent city from seed"
```

---

## Phase 3: Request Lifecycle and Active Slice

### Task 6: Implement request classification and active working set loading

**Objective:** Route player actions to the correct narrow slice of the city.

**Files:**
- Create: `src/lantern_city/orchestrator.py`
- Create: `tests/test_orchestrator.py`

**Step 1: Write failing test**

```python
from lantern_city.orchestrator import classify_request


def test_classify_talk_to_npc():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL — orchestrator missing

**Step 3: Write minimal implementation**

Classify intents such as:
- district_entry
- talk_to_npc
- inspect_location
- case_progress
- generic_action

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add request classification"
```

---

### Task 7: Implement active slice management

**Objective:** Keep only the current city slice hot in memory.

**Files:**
- Create: `src/lantern_city/active_slice.py`
- Create: `tests/test_active_slice.py`

**Step 1: Write failing test**

```python
from lantern_city.active_slice import build_active_slice


def test_active_slice_contains_current_scene_entities():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Create a data structure containing current district, location, scene, NPCs, clues, and case.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/active_slice.py tests/test_active_slice.py
git commit -m "feat: add active working set support"
```

---

## Phase 4: Generation Pipeline

### Task 8: Implement district entry generation

**Objective:** Generate district details only when the player enters or approaches.

**Files:**
- Create: `src/lantern_city/generation/district.py`
- Create: `tests/test_district_generation.py`

**Step 1: Write failing test**

```python
from lantern_city.generation.district import generate_district_detail


def test_district_generation_returns_summary_and_locations():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Return a district summary, 3 locations, local rumors, and NPC anchors.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/generation/district.py tests/test_district_generation.py
git commit -m "feat: add district generation"
```

---

### Task 9: Implement NPC response generation

**Objective:** Generate narrow NPC responses for current conversation context.

**Files:**
- Create: `src/lantern_city/generation/npc_response.py`
- Create: `tests/test_npc_response.py`

**Step 1: Write failing test**

```python
from lantern_city.generation.npc_response import generate_npc_response


def test_npc_response_returns_dialogue_and_updates():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Return:
- dialogue text
- clue updates
- relationship delta
- next actions

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/generation/npc_response.py tests/test_npc_response.py
git commit -m "feat: add NPC response generation"
```

---

### Task 10: Implement clue generation and update logic

**Objective:** Create and update clues as the player investigates.

**Files:**
- Create: `src/lantern_city/clues.py`
- Create: `tests/test_clues.py`

**Step 1: Write failing test**

```python
from lantern_city.clues import add_clue, update_clue_status


def test_add_and_update_clue():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Support statuses like new / confirmed / contradicted / obsolete.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/clues.py tests/test_clues.py
git commit -m "feat: add clue tracking"
```

---

## Phase 5: Progression and Case Logic

### Task 11: Implement progression track updates

**Objective:** Update Lantern Understanding, Access, Reputation, Leverage, City Impact, and Clue Mastery.

**Files:**
- Create: `src/lantern_city/progression.py`
- Create: `tests/test_progression.py`

**Step 1: Write failing test**

```python
from lantern_city.progression import apply_progress_change


def test_progression_tier_advances():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Implement tier thresholds and track-specific updates.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/progression.py tests/test_progression.py
git commit -m "feat: add progression tracking"
```

---

### Task 12: Implement case state transitions

**Objective:** Update case status based on player actions and clues.

**Files:**
- Create: `src/lantern_city/cases.py`
- Create: `tests/test_cases.py`

**Step 1: Write failing test**

```python
from lantern_city.cases import advance_case


def test_case_can_move_from_active_to_solved():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Support active / stalled / escalated / solved / partially_solved / failed.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/cases.py tests/test_cases.py
git commit -m "feat: add case state transitions"
```

---

## Phase 6: Request Handling and Response Composition

### Task 13: Implement the request lifecycle handler

**Objective:** Turn a player request into a state update and response.

**Files:**
- Create: `src/lantern_city/engine.py`
- Create: `tests/test_engine.py`

**Step 1: Write failing test**

```python
from lantern_city.engine import handle_request


def test_handle_talk_request_returns_response():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Load state, generate narrow content, apply consequences, persist updates, return response.
Ensure the response clearly signals meaningful outcomes, including pre-case clue discovery.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/engine.py tests/test_engine.py
git commit -m "feat: add request handler"
```

---

### Task 14: Add response formatting for the player UI

**Objective:** Make outputs concise and readable.

**Files:**
- Create: `src/lantern_city/response.py`
- Create: `tests/test_response.py`

**Step 1: Write failing test**

```python
from lantern_city.response import format_response


def test_response_includes_summary_and_next_actions():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Return narrative text, state changes, and next actions.
Format clue discoveries so the player can tell when something important was found, even before the game can fully explain what it means.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/response.py tests/test_response.py
git commit -m "feat: format player responses"
```

---

## Phase 7: Lazy Background Expansion

### Task 15: Add background pre-generation for one likely next step

**Objective:** Prepare a small amount of future content without over-generating.

**Files:**
- Create: `src/lantern_city/background.py`
- Create: `tests/test_background.py`

**Step 1: Write failing test**

```python
from lantern_city.background import precompute_next_step


def test_precompute_next_step_returns_small_payload():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Return a bounded precomputed summary for one likely scene, district, or NPC branch.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/background.py tests/test_background.py
git commit -m "feat: add background pre-generation"
```

---

## Phase 8: Minimal Interface

### Task 16: Build a minimal playable shell

**Objective:** Provide a basic interface for entering districts and talking to NPCs.

**Files:**
- Create: `src/lantern_city/cli.py` or `src/lantern_city/app.py`
- Create: `tests/test_cli.py`

**Step 1: Write failing test**

```python
from lantern_city.cli import start_game


def test_start_game_bootstraps_city():
    ...
```

**Step 2: Run test to verify failure**

Expected: FAIL

**Step 3: Write minimal implementation**

Support basic input and output loop for the MVP.

**Step 4: Run test to verify pass**

Expected: PASS

**Step 5: Commit**

```bash
git add src/lantern_city/cli.py tests/test_cli.py
git commit -m "feat: add minimal playable shell"
```

---

## Phase 9: Verification and Tuning

### Task 17: Add end-to-end tests for the core loop

**Objective:** Prove that the MVP flow works start to finish.

**Files:**
- Create: `tests/test_end_to_end.py`

**Scenarios:**
- new city seed -> district entry -> NPC talk -> clue update -> case progress
- lantern change -> district update -> clue reliability change
- repeated request -> cached response reuse

---

### Task 18: Measure and tune latency

**Objective:** Ensure lazy generation keeps response time bounded.

**Files:**
- Modify: generation and store modules as needed
- Add timing tests or benchmarks

**Checks:**
- district entry does not over-generate entire city
- NPC responses remain narrow
- cached requests are fast
- background pre-generation is limited

---

## Definition of Done for MVP

The MVP is done when:
- a city can be generated and persisted
- districts can be entered lazily
- NPCs can be talked to with meaningful state changes
- clues update and persist
- cases advance or stall
- progression tracks update
- lantern changes affect play
- the system remains responsive without full-city generation

## Recommended Next Step

Implement Phase 1 first.
Then stop and review the data model before building generation logic.

---

## Post-MVP Depth Direction

Once the MVP/runtime stabilization work is complete, the next major execution phase should follow:

- `briefs/world-turn-and-social-simulation-brief.md`

That phase should be treated as the next systemic depth step for the repo.

### Next recommended build order

1. add a deterministic world-turn engine
2. add idle-delay catch-up based on last meaningful player action
3. expand NPC social persistence and relationship state
4. add faction pressure and operation rules
5. tie case progression to elapsed turns and actor pressure
6. surface time passage and offscreen changes in command output and TUI

### First implementation target

Start with:

- `src/lantern_city/simulation.py`
- `src/lantern_city/app.py`
- `tests/test_simulation.py`

The first deliverable should:

- advance one world turn per meaningful player action
- apply bounded missed turns after player delay
- emit clear player-facing notices about offscreen change

### Runtime boundary

This phase should primarily strengthen `generated_runtime` / evolved-runtime behavior.
If `mvp_baseline` needs lighter or partially bypassed simulation behavior, keep that boundary explicit instead of letting the deeper rules silently become universal.
