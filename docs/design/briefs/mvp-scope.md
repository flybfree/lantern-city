# Lantern City — MVP Scope

## Purpose

This document defines the smallest playable version of Lantern City that still proves the core concept works.

The MVP should demonstrate:
- a seeded city instance
- persistent world state
- a few meaningful NPC agents
- a single investigation case
- lantern-influenced clues and consequences
- lazy generation with bounded latency

## MVP Goal

Prove that a player can:
1. enter a generated city
2. move through at least one district
3. talk to relevant NPCs
4. discover and follow clues
5. affect lantern/state systems
6. advance or stall a case
7. see the city persist and react

## What the MVP Includes

### 1. One generated city seed
The game should generate one coherent Lantern City instance at startup.

Seed should include:
- city mood
- 2 districts
- 1 active case
- 2 factions
- 3 to 5 tracked NPCs
- initial lantern conditions
- initial missingness pressure

### 2. Two playable districts
Keep the MVP focused.

Suggested districts:
- Old Quarter
- one additional district such as Docks or Lantern Ward

Each district should have:
- 3 major locations
- 1 hidden or unlockable location
- district state
- lantern state
- local rumor pool

### 3. One active case
The MVP should center on a single case.

Example case:
- a missing clerk
- a lantern outage
- a record discrepancy
- a faction dispute hidden inside a civic problem

The case should be solvable, but it should also be able to stall or escalate.

### 4. A small NPC set
Track only the NPCs needed for the MVP case.

Suggested set:
- 1 lead NPC
- 1 informant NPC
- 1 gatekeeper NPC
- 1 world/flavor NPC who can become relevant
- optional 1 hidden NPC if needed

Each tracked NPC should have:
- name
- role category
- objectives
- memory
- trust/suspicion state
- clue links

### 5. Core progression tracks
Include the tracks that directly support play:
- Lantern Understanding
- Access
- Reputation
- Leverage
- City Impact
- Clue Mastery

Use tier labels and simple numeric scoring behind the scenes.

### 6. Lantern state effects
Lanterns should matter in a visible way.

The MVP should support at least:
- bright
- dim
- flickering
- extinguished
- altered

And these should affect at least:
- clue reliability
- NPC behavior
- district stability
- access or movement

### 7. Lazy generation and caching
The MVP should not generate the whole city at once.

It should support:
- city seed generation
- district generation on entry
- scene generation on demand
- NPC response generation on demand
- cached summaries and state reuse

### 8. Persistent state
The city should remember changes.

At minimum persist:
- city seed
- city state
- district state
- location state
- NPC state
- case state
- clue state
- player progression state
- lantern state

## What the MVP Does Not Need

Avoid these in the first version:
- all districts from the full design
- many simultaneous cases
- complex faction simulation across the entire city
- deep combat systems
- elaborate inventory systems
- full lore encyclopedia
- perfect procedural generation across every content type
- polished art/UI beyond basic usability

## MVP Player Loop

A good MVP loop is:

1. Start a city seed
2. Enter a district
3. Talk to an NPC
4. Find a clue
5. Inspect or alter lantern state
6. Update case state
7. Unlock a new location or reveal a new lead
8. Resolve or partially resolve the case

## MVP Success Criteria

The MVP is successful if:
- the city feels coherent
- NPCs feel like they have goals and memory
- lanterns change what the player can know or do
- the case system persists across scenes
- the player can make meaningful choices
- generation remains responsive and bounded

## MVP Technical Target

The implementation should prove that:
- cached world objects can be loaded and updated
- generation can happen lazily
- state updates persist across requests
- the player can move through a coherent investigation loop without the whole city being generated up front

## Recommended Build Order

1. Data model and storage
2. Seed generation
3. District entry generation
4. NPC interaction generation
5. Clue/state update engine
6. Case progression and closure
7. UI for basic play
8. Cache and latency tuning

## Design Rule

The MVP should be just enough game to prove that Lantern City is alive, persistent, and responsive.
If a feature does not help prove that, it belongs in a later phase.
