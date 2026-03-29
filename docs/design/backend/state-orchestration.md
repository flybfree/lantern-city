# Lantern City — State Ownership and Orchestration

## Core Principle

The game engine, not the LLM, owns the world state.

The LLM should only receive the minimum relevant context needed for a specific generation task.
The runtime should maintain the full persistent world model and decide what to send, what to cache, and what to update.

## Why This Matters

This separation gives the game:
- consistency across sessions
- efficient token use
- stable persistence
- controllable latency
- deterministic state updates
- easier debugging

If the LLM were asked to remember the whole city, the system would become expensive, inconsistent, and difficult to trust.

## Responsibility Split

### Game engine owns
- all persistent world state
- all IDs and relationships
- all case progression
- all NPC memory and state
- all district, location, and lantern state
- all progression tracks
- all cache invalidation rules
- all persistence and reload behavior

### LLM owns
- generated narrative text
- suggested dialogue
- local scene details
- narrow procedural expansion
- candidate clues or fallout text
- summaries for the active slice only

## State as the Source of Truth

The source of truth must live in structured storage.

That means the game should store and update:
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

Generated text should never replace structured state.
It can describe state, summarize state, or propose updates, but the runtime must validate and commit those updates.

## Relevant Context Selection

Before each LLM call, the orchestrator should build a context packet.

A context packet should include only:
- the current intent
- the active city slice
- the current case
- the current scene
- the relevant district or location
- the specific NPCs involved
- the relevant clues
- the relevant lantern state
- the player’s recent action
- the generation task type

Do not include unrelated districts, NPCs, or cases.

## Context Packet Goal

The goal is not to make the model know everything.
The goal is to give it enough to generate one good narrow response.

Example:
If the player asks one shrine keeper about a lantern outage, the model should see:
- the keeper’s state
- the current district
- the current case
- the nearby lantern state
- the latest clue
- the player’s exact question

It should not see:
- the full city
- every faction plan
- every NPC in the game
- all prior dialogue ever written

## Orchestration Flow

1. Player acts.
2. Runtime classifies the action.
3. Runtime loads only the relevant objects from storage.
4. Runtime composes a minimal context packet.
5. Runtime checks whether cached content already covers the need.
6. If not, runtime calls the LLM with the minimal packet.
7. Runtime validates the LLM output.
8. Runtime translates that output into structured state changes.
9. Runtime persists those state changes.
10. Runtime updates or invalidates caches.
11. Runtime returns a concise player-facing response.

## Efficiency Strategy

### Load narrow
Load only what is needed for the current interaction.

### Generate narrow
Ask the model for one specific result.

### Persist structured updates
Update the source-of-truth objects directly.

### Cache aggressively
Store summaries and short text outputs for reuse.

### Precompute lightly
Only stay one step ahead of the player.

## Example Decision Rules

### When to call the LLM
Call the LLM when:
- a new narrative detail is needed
- an NPC needs a fresh response branch
- a district needs a first-time expansion
- a clue needs interpretation
- fallout needs localized text
- a summary needs refresh after state changes

### When not to call the LLM
Do not call the LLM when:
- cached text already fits the current state
- the action is a simple state lookup
- the request can be answered from stored data alone
- the player is just navigating an already-known area with no new detail needed

## State Update Rule

If the LLM suggests a change, the runtime must still decide whether to accept it.

The engine should validate:
- is the update allowed?
- does it fit the current state?
- does it reference valid IDs?
- does it conflict with known world facts?
- should it update persistence or only a cache?

## Practical Implementation Pattern

A good implementation pattern is:

- store everything as structured JSON in a database
- keep a small active working set in memory
- use cache tables for generated summaries and scene text
- build context packets from the active slice only
- write back only the objects that changed

## Design Rule

The game must be the memory and the orchestrator.
The LLM must be the local content generator.
That split is what makes Lantern City scalable, consistent, and efficient.
