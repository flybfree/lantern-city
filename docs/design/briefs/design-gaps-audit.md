# Lantern City — Design Gaps Audit

## Purpose

This document identifies the major remaining design gaps in Lantern City after the current round of concept, systems, replayability, and backend-oriented documentation.

The goal is not to say the project is underdefined.
The goal is to identify which parts are already strong and which parts still need deeper specification before implementation can proceed cleanly.

## Current Overall Assessment

Lantern City now has a strong foundation in:
- high concept
- tone and mood
- core loop
- lantern and Missingness themes
- measurable progression philosophy
- NPC relevance framing
- replayable seeded city generation
- engine-owned state and narrow-context LLM architecture
- lazy generation and persistence strategy
- backend-oriented storage and orchestration direction

The main remaining gaps are no longer about the game’s identity.
They are about operational design:
- playable content specification
- player-facing interaction structure
- concrete authored MVP content
- rule hardening
- tuning and boundaries

In short:
The project already knows what it is.
It now needs clearer answers for how it is played, how it is authored, and how its systems behave under pressure.

## Gap 1 — District Design Is Still Too High-Level

### Current state
The design brief names the major districts and gives each one a clear thematic identity.
The MVP scope also defines that only two districts are required for the first playable version.

### What is missing
The project still needs full district-level design docs.
Each district should eventually define:
- governing power
- social rules and norms
- local economy
- major locations
- hidden locations
- lantern profile
- local rumor pool
- hidden problem
- typical case patterns
- mechanical identity in play
- access restrictions and unlock conditions

### Evidence
At the time of this audit, the `districts/` folder contained only a README placeholder.
This gap has since been substantially addressed by authored MVP district docs, especially:
- `districts/mvp-old-quarter.md`
- `districts/mvp-lantern-ward.md`

### Why this matters
The districts are currently strong as worldbuilding, but not yet strong as playable systemic spaces.
A player should feel not only that districts look different, but that they produce different investigation pressures and opportunities.

## Gap 2 — Factions Need Full Operational Dossiers

### Current state
The design brief gives each faction a public role and a private goal.
This is enough to establish tone and political texture.

### What is missing
Each faction still needs a proper simulation-facing profile, including:
- resources and assets
- methods of influence
- allies and enemies
- district footprint
- red lines
- preferred leverage types
- recruitment/informant patterns
- reaction logic when threatened
- what success and failure look like for them

### Evidence
At the time of this audit, the `factions/` folder contained only a README placeholder.
This gap has since been substantially addressed by authored MVP faction dossiers, especially:
- `factions/mvp-memory-keepers.md`
- `factions/mvp-shrine-circles.md`
- `factions/mvp-council-of-lights.md`

### Why this matters
Without faction dossiers, factions remain narrative labels rather than durable strategic actors.
The game needs factions to behave like institutions with patterns, not just dramatic names.

## Gap 3 — The MVP NPC Cast Has Not Been Authored Yet

### Current state
The NPC interaction system is well designed.
Role categories, memory, trust, relevance, and interaction purpose are already documented.

### What is missing
The project still needs a concrete MVP cast for the first playable case.
That includes:
- named NPC sheets
- role categories
- visible goals
- hidden goals
- fears and pressures
- relationship links
- clue links
- trust/suspicion starting state
- memory hooks
- criteria for becoming more relevant over time

### Evidence
At the time of this audit, the `npcs/` folder contained only a README placeholder.
This gap has since been substantially addressed by the authored MVP cast doc:
- `npcs/mvp-missing-clerk-cast.md`

### Why this matters
The system for NPCs exists, but the first actual ensemble does not.
The MVP needs a small authored cast that can function as a reference implementation for all later NPC work.

## Gap 4 — The First Playable Case Is Not Fully Authored

### Current state
There are strong docs for case structure and scene structure.
The MVP scope says the first version should revolve around one active case.
Possible case examples have also been suggested.

### What is missing
The MVP needs one complete reference case with:
- opening hook
- true underlying cause
- false leads
- key clues
- clue dependencies
- likely scene paths
- alternate scene paths
- faction involvement
- lantern interaction points
- failure and escalation paths
- possible endings
- aftermath state changes

### Why this matters
The project needs at least one fully authored “gold standard” case to prove the systems work together in actual play.
Without this, the design remains structurally sound but not yet concretely testable.

## Gap 5 — Scene Design Is Conceptual, Not Yet Fully Operational

### Current state
The scene structure doc clearly explains what a scene is, what scene types exist, and how scenes relate to case progression.

### What is missing
The design still needs more operational scene rules, including:
- scene templates by type
- entry triggers
- exit conditions
- stall conditions
- redirect logic
- closure rules
- expected choice density
- scene pacing targets
- player-visible scene state
- guidance for when scenes should remain open versus auto-close

### Why this matters
The project currently knows what scenes are for, but not yet the exact grammar for how scenes should run moment to moment.
That grammar is important for both UX and engine orchestration.

## Gap 6 — The Player Interaction Model Is Still Underdefined

### Current state
The backend request lifecycle is documented.
The API draft exists.
The game is clearly intended to be text-first.

### What is missing
The game still needs a player interaction model that answers:
- Is input free text only, choice-based, or hybrid?
- What actions are always available?
- How are movement and travel expressed?
- How are clues surfaced?
- How is the journal or case board represented?
- How are available actions hinted without over-explaining?
- How does the game help the player recover when stuck?
- What is the relationship between narrative text and structured options?

### Why this matters
This is one of the most important remaining design gaps.
A strong backend architecture does not automatically produce a strong player experience.
The interaction model determines what the game actually feels like to play.

## Gap 7 — Progression Tracks Need Tuning and Unlock Tables

### Current state
Lantern City already has strong progression categories:
- Lantern Understanding
- Access
- Reputation
- Leverage
- City Impact
- Clue Mastery

### What is missing
The design still needs:
- numeric scales and tier boundaries
- unlock thresholds
- gain/loss rules
- soft caps or hard caps
- cross-track interactions
- pacing targets
- expected progression per scene and per case
- run-level progression expectations

### Why this matters
The progression system is measurable in principle, but not yet balanced or implementation-ready.
Until the thresholds and rewards are specified, the tracks are still more descriptive than operational.

## Gap 8 — Lantern and Missingness Rules Need Harder Edges

### Current state
Lanterns and Missingness are among the strongest parts of the project conceptually.
Their thematic role is clear and mechanically promising.

### What is missing
The design still needs sharper rule definitions for:
- clue reliability effects by lantern state
- witness confidence effects by lantern state
- access or traversal effects
- the operational meaning of altered lantern states
- deterministic versus probabilistic effects
- Missingness propagation
- stabilization versus restoration
- permanent loss conditions
- edge-case resolution rules

### Why this matters
Right now these systems are powerful and distinctive, but still somewhat soft at the edges.
Implementation will go more smoothly if their effect boundaries are specified more explicitly.

## Gap 9 — Offscreen Simulation and Time Pressure Need a Formal Model

### Current state
The current docs establish that:
- NPCs can act offscreen
- state persists
- cases can escalate
- the city reacts over time

### What is missing
The project still needs a more formal time and pressure model.
That should answer:
- when time advances
- how urgency is tracked
- how factions move while the player is elsewhere
- how clues decay or go cold
- how unresolved cases worsen
- how pressure rises without punishing exploration too aggressively
- whether clocks, counters, or phases are used

### Why this matters
Persistent state alone does not make the city feel alive.
A city feels alive when offscreen change follows understandable patterns and meaningful pressure.

## Gap 10 — LLM Prompt Contracts Are Not Fully Designed Yet

### Current state
The LLM interface spec is strong at the abstraction level.
It defines task types, structured inputs, JSON outputs, and validation principles.

### What is missing
The project still needs a full prompt contract layer, including:
- actual prompt templates per task type
- schema-specific examples
- valid/invalid output examples
- repair strategies per task
- generation budget guidance
- prose length limits by task
- style guardrails by task
- explicit statements of what the model may not invent

### Why this matters
The interface exists, but the generation behavior is not yet controlled tightly enough for reliable implementation.
This is the difference between “we can call a model” and “we can consistently use a model.”

## Gap 11 — Content Authoring Standards Need a Writing Bible

### Current state
The design brief gives useful tone guidance.

### What is missing
The project still needs a compact writing standard covering:
- prose density
- sentence rhythm
- dialogue style
- clue wording
- narration limits
- how mystery should be implied versus stated
- what kinds of metaphors or clichés to avoid
- how district summaries differ from scene prose
- how NPC voices vary without becoming caricatures

### Why this matters
As the project scales, consistency will become harder.
A writing bible will keep generated and authored content aligned with the game’s tone.

## Gap 12 — Replayability Needs Content Governance

### Current state
Replayability is structurally well designed.
The city seed parameterization and schema work are already strong.

### What is missing
The design still needs clearer replayability rules for:
- what must remain stable across all runs
- what may vary heavily
- what combinations should be disallowed
- how much authored content is reused versus regenerated
- how the MVP case adapts across different seed states
- how replayability preserves identity instead of dissolving it

### Why this matters
A new seed is not enough by itself.
Replayability only works if variation remains coherent and still feels recognizably like Lantern City.

## Gap 13 — End-State and Closure Structure Is Still Loose

### Current state
The project has strong ideas about narrative failure and case escalation.
Failure is meant to create new state rather than simply stop play.

### What is missing
The design still needs clearer closure rules at two levels.

### Case-level closure
The game should define categories such as:
- solved cleanly
- solved politically
- buried
- displaced
- stabilized but unresolved
- catastrophic escalation

### Run-level closure
The MVP should answer:
- when the run ends
- whether one case is the whole MVP arc
- whether the city continues after partial success
- how outcomes are summarized for the player

### Why this matters
The game needs a firmer answer to what it means to finish a case or complete a run.
That answer affects progression, fallout, replayability, and UX.

## What Is Already Strong

The following areas are in relatively good shape and do not appear to be the main blockers right now:
- high concept and setting identity
- tone and atmosphere
- core loop
- district and faction top-line concepts
- lantern and Missingness themes
- stateful world model
- replayable seeded city architecture
- lazy generation philosophy
- engine-owned world state
- backend storage direction
- request lifecycle and state orchestration direction
- API and schema direction

These should still be refined over time, but they are not the biggest current design risks.

## Priority Ranking

If the goal is to maximize progress toward an implementation-ready design, the highest-priority gaps to address next are:

1. Player interaction model
2. One fully authored MVP reference case
3. Concrete MVP NPC cast
4. Two fully specified MVP districts
5. Faction dossiers for the factions used in the MVP case
6. Progression thresholds and unlocks
7. Lantern and Missingness hard rules
8. Prompt contracts by generation task

## Recommended Next Step

The most valuable next document is:
- `mechanics/player-interaction-model.md`

That document should define how the game is actually played from moment to moment.
Once that is clear, the next best step is:
- `cases/mvp-reference-case.md`

That pairing would connect the strong existing system architecture to an actual playable experience.

## Summary

Lantern City is no longer blocked by concept formation.
It is now in the transition from strong speculative design to executable game design.

The biggest remaining work is to define:
- player-facing interaction structure
- one concrete authored playable slice
- the hard edges of the core systems

Once those are specified, the design should be in a strong position to support implementation planning and eventually coding.