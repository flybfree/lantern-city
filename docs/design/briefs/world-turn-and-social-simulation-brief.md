# Lantern City — World Turn and Social Simulation Brief

## Purpose

This brief defines the next systemic depth layer for Lantern City:

- more durable NPC social reality
- faction and NPC offscreen action
- a real world-turn model
- case progression that advances when the player delays

This is a post-MVP depth brief.
It should strengthen the evolved runtime without breaking the authored MVP baseline loop.

## Core Design Goal

Make the city feel active even when the player is not directly touching every actor.

That means:

- NPCs should remember more than the current conversation
- NPCs should have changing attitudes toward the player, other NPCs, and factions
- factions should apply pressure and pursue goals offscreen
- cases should worsen, mutate, or narrow when neglected
- delay should matter

The player should feel that time passes, opportunities narrow, and people react to history.

## Boundary With Existing Runtime Layers

This system belongs primarily to the `evolved_runtime`.

Rules:

- `generated_runtime` should use this system as the default direction
- `mvp_baseline` may use a much lighter or partially disabled version
- do not force the authored Missing Clerk onboarding loop to simulate full-world complexity unless explicitly intended
- do not let the MVP shortcut path define the general rule for time, relationships, or offscreen action

Practical interpretation:

- the baseline can keep a reduced turn model or scripted exceptions
- the full simulation should become the standard for generated cases and broader play

## Design Principle

Do not build a continuously running background simulation first.

Instead, build:

- a deterministic `world turn` system
- with `idle-delay catch-up`

Meaning:

- every meaningful player action advances the world at least one turn
- if the player waits too long between turns, the next interaction applies one or more missed world turns
- world advancement is processed in discrete, testable steps

This preserves:

- testability
- persistence simplicity
- CLI/TUI compatibility
- player legibility

## Why This Matters

Without this layer:

- NPCs remain too reactive and too local
- factions feel more like lore than active institutions
- cases wait for the player instead of resisting delay
- clue and pressure systems stay shallow

With this layer:

- social consequences accumulate
- access changes because of history, not just command order
- urgency becomes real
- cases can feel political, fragile, and contested

## Required Outcomes

The implemented system should support all of the following.

### 1. NPC social persistence

NPCs should remember:

- recent player questions
- promises made or broken
- favors, humiliations, threats, rescues, and betrayals
- which other NPCs they trust, fear, avoid, or depend on
- faction pressure currently affecting them
- whether the current investigation is becoming dangerous

### 2. NPC offscreen agency

NPCs should be able to:

- move between plausible locations
- hide, obstruct, negotiate, warn, search, or withdraw
- pass information to other NPCs or factions
- become harder or easier to reach
- change tone and willingness based on evolving state

### 3. Faction activity

Factions should:

- maintain current goals and local operations
- pressure NPCs, districts, and cases
- change the social landscape around a case
- create mechanical consequences beyond prose flavor

### 4. Time-sensitive case progression

Cases should:

- escalate when neglected
- shift witness availability
- narrow evidence windows
- harden false narratives
- alter district posture and local pressure

### 5. Player-visible time

The player must be able to tell:

- that time passed
- how much time passed
- what changed because of it
- what became more urgent or more difficult

Hidden simulation is not enough.
If delay matters, delay must be surfaced.

## World Turn Model

The city should advance through discrete world turns.

### Basic rule

- every meaningful player action advances one world turn

Meaningful actions include:

- moving districts
- entering locations
- talking to an NPC
- inspecting a location or object
- attempting case advancement
- other actions that consume investigative attention

Pure UI/help actions do not need to advance time.

### Idle-delay rule

If the player waits longer than a configured threshold, the next meaningful interaction should apply one or more missed world turns.

Recommended initial approach:

- persist the wall-clock time of the last meaningful player action
- on the next meaningful action, compute idle duration
- convert long idle delay into `missed_turns`
- cap the number of catch-up turns per interaction to avoid runaway punishment

This should be strict enough to matter, but bounded enough to remain fair.

### Initial recommendation

Start with:

- `1` world turn per meaningful player action
- `+1` missed turn for each idle interval threshold crossed
- a conservative cap such as `3` missed turns on catch-up

Tune later after playtesting.

## Turn Advancement Pipeline

Each world turn should process in a stable order.

Recommended order:

1. increment `CityState.time_index`
2. update city-level timing markers
3. tick faction plans
4. tick focused NPC intents and movement
5. tick warm/background NPC state abstractly
6. advance case pressure and offscreen case consequences
7. apply clue risk/decay/corroboration-window changes
8. apply district and lantern side effects if relevant
9. collect player-facing notices for what changed

The order should stay deterministic so the behavior is testable and debuggable.

## NPC Social Model

The current model already has:

- `trust_in_player`
- `fear`
- `suspicion`
- `relationships`
- `memory_log`
- `recent_events`

That is the right base.
The next step is to make it more structured and consequential.

### NPC state additions

Add or formalize fields such as:

- `current_intent`
- `intent_target_id`
- `routine_profile`
- `last_seen_player_turn`
- `last_meaningful_interaction_turn`
- `social_stance_by_npc`
- `faction_stance_by_faction`
- `owed_favors`
- `grievances`
- `commitment_flags`
- `memory_summary`

Not all of these need to ship in the first slice.
But the model must clearly distinguish:

- stance toward player
- stance toward other NPCs
- stance toward factions
- recent event memory
- durable social consequences

### Relationship model

Relationship state should support at least:

- trust
- suspicion
- fear
- dependence
- debt
- rivalry
- status
- last_updated_at
- last_changed_turn

This can extend the existing `RelationshipSnapshot` rather than replacing it outright.

### Memory model

Do not rely on one flat `memory_log` forever.
Conceptually split memory into:

- episodic memory:
  what happened
- social memory:
  what the NPC now thinks of someone
- commitment memory:
  promises, favors, threats, betrayals
- rumor memory:
  secondhand information with confidence

The first implementation can keep one persisted log but should begin tagging memory entries by type.

## Faction Activity Model

Factions should stop being primarily descriptive objects.

### Faction state additions

Add or formalize fields such as:

- `active_goal`
- `current_operation`
- `operation_target_ids`
- `heat`
- `stance_by_case`
- `stance_by_npc`
- `last_action_turn`

### Faction actions

A faction turn does not need to be huge.
It only needs to do something legible.

Examples:

- pressure a witness
- secure a location
- spread a preferred narrative
- cool down public scrutiny
- compete with another faction over a district node

The point is not cinematic spectacle.
The point is persistent institutional pressure.

## Case Evolution Under Time

Current case pressure already supports:

- `pressure_level`
- `time_since_last_progress`
- `offscreen_risk_flags`
- `active_resolution_window`

That should now be connected to actual actor behavior.

### Cases should be able to

- gain or lose witness access
- shift where evidence can be found
- increase district scrutiny
- produce new obstruction or urgency tags
- move from local contradiction to public pressure

### Case state additions

Add or formalize fields such as:

- `deadline_turn`
- `offscreen_progress_clock`
- `blocking_actor_ids`
- `at_risk_clue_ids`
- `next_pressure_event`

## Simulation Scope Rules

Do not simulate every actor with equal depth every turn.

Use actor temperature tiers:

- focused:
  current district, current case, recently contacted NPCs
- warm:
  directly linked actors for the active investigation
- cold:
  everyone else

Focused actors get richer updates.
Warm actors get simpler updates.
Cold actors update rarely or abstractly.

This is important for both clarity and implementation cost.

## Player-Facing UX Requirements

This system will fail if it only exists in backend state.

The player must get:

- clear turn advancement feedback
- a visible time or turn indicator
- summaries of important offscreen changes
- clear pressure escalation messages
- reminders when relationships materially shift

Good examples of surfaced changes:

- a witness is avoiding you now
- the district is under tighter watch
- the case window is narrowing
- a faction leaned on someone overnight
- an NPC moved or sent word elsewhere

## Recommended Module Direction

Likely target modules:

- `src/lantern_city/models.py`
- `src/lantern_city/app.py`
- `src/lantern_city/engine.py`
- `src/lantern_city/cases.py`
- `src/lantern_city/tui.py`
- `src/lantern_city/generation/npc_response.py`

Recommended new modules:

- `src/lantern_city/social.py`
- `src/lantern_city/simulation.py`
- `src/lantern_city/factions.py`

Possible responsibilities:

- `social.py`
  relationship and memory update rules
- `simulation.py`
  world-turn advancement and idle catch-up orchestration
- `factions.py`
  faction plan and pressure rules

## Suggested First Implementation Slice

Build this in three slices.

### Slice 1 — World turn engine

Implement:

- `advance_world_turn(...)`
- last-meaningful-action timestamp persistence
- idle-delay to missed-turn conversion
- player-facing change summary

This is the safest first slice because it creates the execution spine for everything else.

### Slice 2 — Social persistence

Implement:

- relationship model expansion
- memory entry typing/tagging
- NPC-player and NPC-NPC relationship update rules
- player-facing social change surfacing

### Slice 3 — Intent and faction pressure

Implement:

- NPC intents
- faction operations
- case actor pressure integration
- movement, obstruction, and negotiation outcomes

## Testing Priorities

This system needs behavior tests, not only object-shape tests.

Add tests for:

- one action advances exactly one world turn
- idle delay produces bounded catch-up turns
- pure help/status commands do not advance time
- NPC memory entries survive persistence
- relationship changes alter later dialogue context
- faction actions can affect case pressure
- offscreen world advancement produces player-facing notices
- baseline mode keeps its intended reduced behavior
- generated runtime uses the deeper turn model

Likely test files:

- `tests/test_simulation.py`
- `tests/test_social.py`
- `tests/test_factions.py`
- `tests/test_relationship_persistence.py`
- `tests/test_case_pressure.py`

## Failure Modes To Avoid

- hidden punishment with no surfaced explanation
- every action feeling equally expensive regardless of importance
- every NPC changing every turn in noisy, unreadable ways
- turning the MVP baseline into a fragile simulation showcase
- letting world turns become so punishing that investigation becomes anti-exploration
- encoding major social meaning only in prose instead of state

## Definition Of Done

This feature is in good shape when:

- NPCs feel historically consistent rather than turn-local
- delay creates visible but legible consequences
- factions exert pressure through state changes, not only flavor text
- cases evolve when ignored
- the player can read what changed and why
- generated runtime feels more alive without making baseline onboarding collapse

## Summary

Lantern City already has the beginnings of this system:

- a city time index
- NPC memory
- relationship snapshots
- offscreen NPC updates
- case pressure

The next step is to unify those into a real world-turn simulation with durable social state.

That is the right direction if the goal is to make the city feel inhabited, political, and resistant to passive play.
