# Lantern City — Sequence Diagrams

## 1. Player Enters a District

```text
Player
  -> UI: choose district
  -> Orchestrator: request district entry
  -> State Store: load CityState + DistrictState summary
  -> Cache Layer: check for cached district details
  -> Generator: fill missing district detail if needed
  -> State Store: persist updated DistrictState
  -> Rule Engine: update access, tension, lantern effects if relevant
  -> UI: show district description + relevant NPCs + available actions
```

### Notes
- The system should prefer cached district summaries if they exist.
- Only generate extra detail for the player’s immediate path.
- If the district has been visited before, reuse prior state and only generate changed elements.

## 2. Player Talks to an NPC

```text
Player
  -> UI: select NPC / ask question
  -> Orchestrator: start conversation scene
  -> State Store: load NPCState + CaseState + related ClueState
  -> Cache Layer: check for existing conversation context
  -> Generator: produce response branch for current question
  -> Rule Engine: update relationship / access / leverage / clue state
  -> State Store: persist NPCState + updated tracks
  -> UI: show response + progress feedback + exit/continue options
```

### Notes
- The NPC response should be generated narrowly around the current question.
- If the NPC is only a rumor source, the conversation should end quickly.
- If the NPC becomes relevant, expand the branch and update state.

## 3. Player Investigates a Location

```text
Player
  -> UI: inspect location/object
  -> Orchestrator: request investigation scene
  -> State Store: load LocationState + LanternState + relevant ClueState
  -> Cache Layer: check for location summary and known hidden features
  -> Generator: add only the needed investigative detail
  -> Rule Engine: reveal clues, update lantern effects, alter case state
  -> State Store: persist LocationState + ClueState + CaseState
  -> UI: present findings and next actions
```

### Notes
- Investigation should reveal structured evidence, not just prose.
- If lantern state is involved, update the local district effects immediately.

## 4. Player Makes a Choice That Changes State

```text
Player
  -> UI: choose action
  -> Orchestrator: submit action
  -> State Store: load all impacted entities
  -> Rule Engine: evaluate consequences
  -> Generator: produce fallout text or new scene hooks if needed
  -> State Store: persist updated entities
  -> UI: show outcome, progress changes, and new situation
```

### Notes
- This is where reputation, leverage, and city impact should change.
- The game should avoid regenerating the whole city; only the impacted slice should update.

## 5. Case Advances or Closes

```text
Player action / scene outcome
  -> Rule Engine: detect case threshold reached
  -> CaseState: update status (active / stalled / solved / failed / escalated)
  -> State Store: persist case outcome
  -> Generator: create fallout, next leads, or closure summary
  -> CityState: update district/faction consequences
  -> UI: show case result and what changed in the city
```

### Notes
- Cases should always leave the city in a new state.
- Solving a case should unlock new possibilities, not just a completion badge.

## 6. Background Lazy Expansion

```text
Player is active in current scene
  -> Orchestrator: detects likely next area
  -> Generator: precompute one nearby district / NPC / scene candidate
  -> Cache Layer: store the result
  -> State Store: keep it dormant until needed
```

### Notes
- This keeps future interactions fast without generating too far ahead.
- Only one step ahead should be prepared aggressively.

## Implementation Rule

All sequences should follow the same general pattern:
1. Load only the relevant cached state.
2. Generate only the missing detail needed now.
3. Apply state changes.
4. Persist the results.
5. Return a concise player-facing response.

That is how Lantern City stays responsive while still feeling deep and persistent.
