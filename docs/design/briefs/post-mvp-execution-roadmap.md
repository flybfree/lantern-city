# Lantern City — Post-MVP Execution Roadmap

## Purpose

This document turns the current design goals into a repo-specific execution roadmap.
It is not a replacement for the original MVP implementation plan.
It exists because the repository is already beyond the original MVP bootstrap stage:
- persistent models exist
- SQLite persistence exists
- active-slice loading exists
- the TUI exists
- city seed generation exists
- world content generation exists
- generated case support exists

The remaining work is now about raising the simulation depth, replay value, and social persistence so the game behaves more like the intended Lantern City and less like a narrow vertical slice with generation attached.

## Current Read of the Codebase

The current implementation spine is concentrated in:
- `src/lantern_city/models.py`
- `src/lantern_city/store.py`
- `src/lantern_city/bootstrap.py`
- `src/lantern_city/active_slice.py`
- `src/lantern_city/orchestrator.py`
- `src/lantern_city/engine.py`
- `src/lantern_city/app.py`
- `src/lantern_city/tui.py`
- `src/lantern_city/lanterns.py`
- `src/lantern_city/clues.py`
- `src/lantern_city/cases.py`
- `src/lantern_city/progression.py`
- `src/lantern_city/generation/*`

This means the main opportunity is not to build missing infrastructure first.
It is to deepen the runtime rules and state transitions already present.

## Strategic Goal

Move Lantern City from:
- one playable generated city with a narrow investigative loop

to:
- a replayable city-state simulation where
- seed variation meaningfully changes a run
- NPCs develop durable relationships with the player
- NPCs and factions act offscreen
- cases evolve under pressure
- lantern and Missingness conditions drive actual play consequences
- case outcomes leave visible, persistent civic fallout

This roadmap should now be read alongside:
- `briefs/world-turn-and-social-simulation-brief.md`

That brief turns the next major depth target into a concrete execution direction:
- durable NPC social memory
- faction and NPC offscreen action
- discrete world turns
- idle-delay catch-up
- time-sensitive case progression

## Boundary With The MVP Loop

The repo still carries an authored MVP vertical slice that serves as:
- the onboarding path
- the regression-test path
- the shortest proof that the loop works at all

That baseline should remain playable.
But post-MVP work should not treat its simplified assumptions as the default rule for the full game.

In practical terms:
- the authored Missing Clerk shortcut path can remain as a controlled baseline
- deeper runtime systems should be free to demand more friction, broader evidence, and stronger offscreen evolution
- when shared logic must support both, the distinction should be explicit rather than accidental

## Priority Order

Implement in this order:

1. world turn engine and idle-delay simulation
2. NPC agency and relationship persistence
3. case pressure and offscreen evolution
4. seed-driven city variation hardening
5. interaction-model strengthening and clue synthesis
6. lantern and Missingness rule deepening
7. authored content expansion on top of stronger systems

This order matters.
More authored content on top of shallow simulation will still feel shallow.
Stronger simulation immediately improves both authored and generated play.

The key refinement here is that relationship persistence and case escalation should now be built on top of an explicit world-turn spine rather than remaining as loosely connected per-command updates.

## Phase 0 — World Turn Engine and Idle-Delay Simulation

## Goal

Create a deterministic world-turn system that advances on meaningful player actions and catches up when the player waits too long between turns.

## Current state

The code already contains:
- `CityState.time_index`
- app-owned case pressure updates
- app-owned offscreen NPC updates
- NPC memory logs and relationship snapshots

What is missing is a unified turn engine that ties these together and makes delay matter explicitly.

## Required outcomes

The runtime should:
- advance one world turn on each meaningful player action
- convert long real-time delay into bounded missed-turn catch-up
- surface player-facing notices about what changed
- support deeper generated-runtime behavior without forcing full simulation onto the MVP baseline path

## Target modules

- `src/lantern_city/models.py`
- `src/lantern_city/app.py`
- `src/lantern_city/engine.py`
- `src/lantern_city/tui.py`
- new modules such as:
  - `src/lantern_city/simulation.py`
  - `src/lantern_city/social.py`
  - `src/lantern_city/factions.py`

## Concrete work

### 1. Define meaningful-action turn advancement

Advance time for:
- district movement
- location entry
- inspection
- NPC conversation
- case actions

Do not advance time for pure help/status surfaces unless intentionally chosen later.

### 2. Add idle-delay catch-up

Persist the last meaningful-action timestamp.
On the next meaningful action:
- compute idle delay
- translate that into missed turns
- cap the number of applied catch-up turns

### 3. Centralize world advancement

Replace ad hoc per-command offscreen updates with a stable turn pipeline that can:
- increment city time
- tick faction plans
- tick focused/warm/cold NPCs
- advance cases
- update clue risk windows
- emit player-facing notices

### 4. Surface time clearly

The TUI and command outputs should make it clear:
- that time passed
- how much passed
- what changed because of it

## Exit criteria

- delay matters in generated runtime
- the player can read the consequences of time passing
- the system remains deterministic enough for behavior testing
- the MVP baseline can still preserve its lighter onboarding behavior intentionally

## Phase 1 — NPC Agency and Relationship Persistence

## Goal

Make NPCs durable social actors rather than conversation endpoints.

## Current state

The repo already has the right state shape for this in `NPCState`:
- trust
- fear
- suspicion
- loyalty
- current objective
- hidden objective
- memory log
- known clues

But most of the live behavior is still player-triggered rather than independently evolving.

## Required outcomes

NPCs should:
- remember the player across scenes and turns
- change stance based on trust, fear, suspicion, promises, and leverage
- move between locations when appropriate
- react to district pressure and faction pressure
- change what they are willing to say or hide over time
- build or damage relationships with other NPCs offscreen

## Target modules

- `src/lantern_city/models.py`
- `src/lantern_city/app.py`
- `src/lantern_city/engine.py`
- `src/lantern_city/active_slice.py`
- `src/lantern_city/generation/npc_response.py`
- `src/lantern_city/response.py`

## Concrete work

### 1. Expand NPC state

Add fields to `NPCState` for:
- `relationship_map`: other NPC or faction relationships
- `schedule_or_anchor_pattern`: where they tend to appear
- `offscreen_state`: idle, hiding, searching, obstructing, escalating, negotiating
- `recent_events`: compact list of non-player-triggered changes
- `player_flags`: promises, betrayals, rescues, humiliations, favors

### 2. Add relationship update rules

Create explicit helper logic, probably in a new module such as:
- `src/lantern_city/social.py`

That logic should update:
- trust
- suspicion
- fear
- willingness to disclose
- willingness to grant access
- willingness to redirect to another NPC

### 3. Add offscreen NPC ticks

Introduce an offscreen update pass after meaningful actions.
This does not need to be a full simulation.
For the MVP-plus stage, one narrow update pass per turn is enough.

Likely home:
- `src/lantern_city/app.py`
- or a new `src/lantern_city/simulation.py`

### 4. Make generated dialogue reflect persistent stance

`generation/npc_response.py` already carries emotional and social context.
That should be extended so the generator sees:
- recent relationship changes
- recent promises and betrayals
- whether the NPC is under outside pressure
- whether the NPC is trying to use the player

## Exit criteria

- the same NPC gives meaningfully different answers later in the run
- NPCs can relocate or become harder/easier to find
- the player can build durable trust or lasting hostility
- NPC state can change even if the player does not talk to that NPC directly every turn

## Phase 2 — Case Pressure and Offscreen Evolution

## Goal

Cases should evolve if neglected.
They should not wait in suspended animation for `case <id>`.

## Current state

The code has:
- `CaseState`
- case generation and bootstrap
- case resolution paths
- some clue reliability updates

But case evolution is still too static compared to the design intent.

## Required outcomes

Cases should:
- escalate when delayed
- harden false official narratives
- move witnesses or evidence
- alter access conditions
- allow stabilization, containment, public exposure, or burial
- change district pressure while active

## Target modules

- `src/lantern_city/models.py`
- `src/lantern_city/cases.py`
- `src/lantern_city/app.py`
- `src/lantern_city/lanterns.py`
- `src/lantern_city/clues.py`
- `src/lantern_city/generation/case_generation.py`

## Concrete work

### 1. Expand case state

Add fields to `CaseState` for:
- `pressure_level`
- `time_since_last_progress`
- `offscreen_risk_flags`
- `active_resolution_window`
- `district_effects`
- `npc_pressure_targets`

### 2. Add case progression rules separate from final resolution

Create rules for:
- `advance_pressure(case, city, district_states, npcs)`
- `apply_case_escalation(...)`
- `apply_case_stabilization(...)`

This belongs in:
- `src/lantern_city/cases.py`

### 3. Make clues change under pressure

Clues should be able to:
- remain stable
- become uncertain
- become contradicted
- gain urgency
- move location

This should be constrained and legible, not random.

### 4. Surface pressure in the UI

The TUI should show:
- case pressure
- district posture
- whether a case is stabilizing, rising, or urgent

Primary files:
- `src/lantern_city/tui.py`
- `src/lantern_city/response.py`

## Exit criteria

- waiting has visible case consequences
- unresolved investigations become harder, stranger, or more political over time
- cases mutate without feeling arbitrary
- the player can feel the difference between acting early and acting late

## Phase 3 — Seed-Driven City Variation Hardening

## Goal

Make each generated city materially different in play.

## Current state

Seed generation exists, but the next-level requirement is stronger:
the seed must change actual pressure, access, and social topology, not only names and prose.

## Required outcomes

A different city seed should change:
- faction influence distribution
- district composition and role emphasis
- lantern condition map
- Missingness target domains
- NPC network topology
- available case patterns
- likely investigative routes

## Target modules

- `src/lantern_city/seed_schema.py`
- `src/lantern_city/bootstrap.py`
- `src/lantern_city/generation/city_seed.py`
- `src/lantern_city/generation/world_content.py`
- `src/lantern_city/generation/case_generation.py`
- `src/lantern_city/data/default_seed.json`

## Concrete work

### 1. Enrich the city seed

Add fields for:
- district role weights
- faction conflict profile
- seed-level case bias tags
- district social rules
- altered lantern target domains
- Missingness propagation style
- city-level stability profile

### 2. Make world generation depend on seed traits

District locations, case hooks, NPC roles, and clue structures should all reflect seed conditions.
`world_content.py` and `case_generation.py` should consume those seed traits directly rather than just using them as loose flavor.

### 3. Add replayability guardrails

Define:
- what always remains Lantern City
- what can vary hard
- what combinations are disallowed

This is partly a doc task and partly a generator validation task.

## Exit criteria

- two seeds produce materially different investigation flow
- district/faction differences are visible in mechanics, not just prose
- replayability preserves identity instead of drifting into arbitrary generation

## Phase 4 — Interaction Model Strengthening and Clue Synthesis

## Goal

Make the moment-to-moment play loop closer to the intended hybrid investigation model.

## Current state

The TUI and command loop are functional, but the game still leans more command-shell than guided investigative scene model.

## Required outcomes

The player should always be able to understand:
- where they are
- who matters here
- what is interactable
- what changed
- which leads are strongest
- how close a case is to resolution or collapse

## Target modules

- `src/lantern_city/tui.py`
- `src/lantern_city/app.py`
- `src/lantern_city/response.py`
- `src/lantern_city/engine.py`
- `src/lantern_city/clues.py`

## Concrete work

### 1. Add scene affordance structure

Every response should get more explicit about:
- visible NPCs
- notable objects
- exits
- case relevance
- meaningful next actions

### 2. Add clue synthesis actions

Support actions like:
- compare two clues
- test a contradiction
- ask what changed
- ask what matters here
- ask who is most relevant now

This can begin as engine-owned helper actions before deeper LLM support.

### 3. Improve case-board style summaries

Add compact views for:
- strongest leads
- unresolved questions
- reliable vs unstable clues
- active NPC pressure points

## Exit criteria

- the player no longer has to infer core affordances from prose alone
- clue accumulation becomes clue interpretation
- the interface helps recover from stuck states without solving the mystery automatically

## Phase 5 — Lantern and Missingness Rule Deepening

## Goal

Make lanterns and Missingness the primary differentiator in actual play.

## Current state

The conceptual design is strong.
The runtime uses some lantern effects, especially around clue reliability, but the full systemic reach is not yet realized.

## Required outcomes

Lantern and Missingness should visibly affect:
- witness confidence
- clue reliability
- route certainty
- access legitimacy
- district posture
- rumor quality
- resolution quality

## Target modules

- `src/lantern_city/lanterns.py`
- `src/lantern_city/clues.py`
- `src/lantern_city/app.py`
- `src/lantern_city/models.py`
- `src/lantern_city/generation/location_inspection.py`
- `src/lantern_city/generation/npc_response.py`

## Concrete work

### 1. Add explicit lantern-state effect helpers

The code should expose deterministic rule helpers for:
- witness confidence shift
- route certainty shift
- document distortion risk
- physical-evidence resilience
- altered-target selective distortion

### 2. Add Missingness propagation support

Track propagation between:
- person
- record
- route
- event
- place

Start narrow.
Do not build a massive simulation first.
Just support legible cross-object pressure.

### 3. Separate stabilization from restoration in runtime outcomes

The engine should be able to say:
- stabilized but not restored
- restored privately
- restored publicly
- permanently damaged

That distinction is central to the game’s identity.

## Exit criteria

- the player can learn lantern/Missingness rules through play
- physical evidence, testimony, and records feel different under different conditions
- outcomes are shaped by state, not just by clue count

## Phase 6 — Content Expansion on Top of Stronger Systems

## Goal

Use the stronger runtime to deepen authored and generated content.

## Required outcomes

- more authored reference cases
- more district-specific case patterns
- richer faction behaviors
- stronger NPC ensemble interplay
- better replay quality from seed differences

## Target modules

- `src/lantern_city/generation/case_generation.py`
- `src/lantern_city/generation/world_content.py`
- `src/lantern_city/generation/npc_response.py`
- design docs under `docs/design/`

## Concrete work

### 1. Add one more authored case after the systemic work lands

Do not do this first.
Use it to validate the improved simulation.

### 2. Expand district-specific content grammars

Generated clues, hooks, and NPCs should vary by district logic, not just by words.

### 3. Add stronger faction reaction patterns

Faction responses to outcomes should be durable and mechanically visible.

## Cross-Cutting Testing Priorities

The next stage needs more than unit tests for object creation.
It needs behavior tests.

Add tests for:
- offscreen NPC state transitions
- case pressure escalation
- seed variation producing different world structure
- clue reliability changes under different lantern states
- relationship persistence across multiple conversations
- resolution differences caused by stabilization vs restoration

Likely files:
- `tests/test_social.py`
- `tests/test_case_pressure.py`
- `tests/test_seed_variation.py`
- `tests/test_lantern_rules.py`
- `tests/test_relationship_persistence.py`

## Recommended First Implementation Slice

The best first slice is:

1. expand `NPCState`
2. add a small `social.py` rules module
3. add one offscreen NPC update pass in `app.py`
4. thread new stance/pressure data into `generation/npc_response.py`
5. surface relationship changes in `response.py` and `tui.py`

Why this first:
- it immediately improves the current game feel
- it supports both authored and generated content
- it creates the foundation for case pressure and offscreen evolution

## Definition of Done for the Next Level

Lantern City reaches the next level when:
- a new seed materially changes the run
- NPCs remember, evolve, and act on their own
- cases escalate or mutate if neglected
- clue interpretation matters as much as clue discovery
- lanterns and Missingness change what can be known and done
- case outcomes leave persistent civic consequences
- the city feels like a living memory machine, not a static mystery shell

## Summary

The repo no longer needs a blank-slate MVP plan.
It needs a depth plan.

That plan should prioritize:
- simulation depth before content breadth
- social persistence before more authored prose
- systemic replayability before more surface variation

If this roadmap is followed, Lantern City should move much closer to its actual promise:
a replayable investigative city where truth, light, memory, and institutions all push back.
