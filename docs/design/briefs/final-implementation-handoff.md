# Lantern City — Final Implementation Handoff

## Purpose

This document is the final design-to-implementation handoff brief for the Lantern City MVP.
It exists to give a future implementation pass one clean starting point that says:
- what to build
- where the source of truth lives
- what constraints must not be broken
- how to execute the build safely
- how to review work before advancing

This is the brief a controller agent or human implementer should read before starting code work.

## Current Project Status

Lantern City is now past the early concept phase.
The MVP design spine is complete enough to support implementation.

The workspace now includes:
- a canonical design brief
- a scoped MVP definition
- a player interaction model
- a reference MVP case
- a concrete MVP NPC cast
- two authored MVP districts
- three authored MVP factions
- operational progression thresholds and unlocks
- operational lantern and Missingness rules
- generation prompt contracts
- writing standards
- backend-facing schema and orchestration docs
- implementation and subagent execution plans
- a canonical document index

This means implementation can now proceed without needing to invent the game’s core design during coding.

## Primary Handoff Rule

Before writing or reviewing code, use:
- `briefs/canonical-doc-index.md`

That file is the document map for the current source-of-truth set.
If two docs disagree, prefer the canonical document named in the index.

## Implementation Objective

Build the smallest playable Lantern City MVP that proves all of the following in one coherent loop:
- a seeded city instance
- persistent world state
- the Old Quarter and Lantern Ward as MVP districts
- one active case: The Missing Clerk
- a small tracked NPC cast with memory and motive
- measurable progression through access, clue work, leverage, and lantern understanding
- lantern and Missingness effects that change information quality and access
- a hybrid text-first interaction model
- narrow, validated LLM generation
- persistent fallout after case resolution

## What Counts as Success

Implementation is successful when a player can:
1. start a new city instance
2. enter the Old Quarter
3. investigate the missing clerk case
4. talk to named NPCs and get different value from each
5. discover and revise clues
6. inspect lantern-linked evidence
7. unlock restricted or hidden spaces
8. reach Tovin Vale by one or more plausible routes
9. resolve the case through at least one meaningful ending path
10. see the city remember the consequences

## MVP Baseline vs Evolved Runtime

Lantern City now has two valid design layers that must not be conflated:

### 1. MVP vertical slice baseline

This is the short, controlled authored loop used to prove the game works end to end.

Its purpose is:
- onboarding
- regression testing
- fast verification that the core loop still functions
- preserving a deterministic proof-of-play path for The Missing Clerk

This baseline is allowed to be simpler than the eventual full game.
In particular, it may keep:
- a shorter clue chain
- a faster case introduction
- a narrower resolution path
- less friction than the full simulation would eventually use

### 2. Evolved simulation runtime

This is the deeper game layer where:
- latent cases can stay hidden until properly surfaced
- offscreen pressure can move a case from active to stalled or escalated
- broader clue interpretation matters
- NPC and district state can evolve independently of the player
- resolution can demand more than the vertical-slice shortcut path

### Rule for future implementation

Do not let assumptions from the MVP vertical slice silently hard-code the full runtime.
If a behavior exists only to preserve the MVP showcase loop, treat it as authored baseline behavior, not as the general rule for all future cases and systems.

Likewise, do not let deeper simulation rules accidentally erase the baseline proof-of-loop path that the current tests and onboarding flow still depend on.

When there is tension between the two:
- preserve the MVP baseline intentionally
- document the shortcut clearly
- keep the deeper rule as the default direction for post-MVP systems
- avoid mixing the two by accident inside shared logic without comment

## Post-MVP Depth Direction

The next major systems phase after current MVP/runtime stabilization should follow:

- `briefs/world-turn-and-social-simulation-brief.md`

That brief defines the next evolved-runtime target:

- deterministic world turns
- idle-delay catch-up when the player waits too long
- deeper NPC memory and relationship persistence
- faction pressure and offscreen action
- case evolution tied to elapsed turns and social pressure

### Implementation rule for that phase

Do not introduce hidden real-time simulation first.
Prefer a discrete, testable world-turn system that:

- advances on meaningful player actions
- can apply bounded catch-up turns
- surfaces what changed to the player clearly

### Baseline protection rule

This depth work should primarily strengthen `generated_runtime` / evolved-runtime play.
If the authored `mvp_baseline` loop needs lighter or partially disabled simulation behavior, preserve that intentionally rather than forcing the onboarding path into full simulation complexity by accident.

## MVP Build Boundaries

Do build:
- core runtime models
- persistence layer
- seed generation and validation
- narrow generation interface
- district and location loading
- NPC response generation
- clue creation and update logic
- progression updates
- lantern and Missingness rule application
- case advancement and fallout
- minimal CLI or equivalent terminal-first interface

Do not expand scope during the MVP build into:
- additional full districts beyond the authored MVP pair
- combat systems
- large inventory systems
- multiple simultaneous fully-authored cases
- broad sandbox generation outside the narrow request model
- UI polish beyond what is needed for clear play

## Non-Negotiable Design Constraints

These constraints are central to Lantern City and must survive implementation.

### 1. Engine-owned state
The game engine owns all persistent truth.
The LLM is never the world model.

### 2. Narrow generation only
Every LLM call must be scoped to one task and one active context slice.
No giant whole-world prompts.

### 3. Hybrid interaction model
The player experience must remain:
- structured enough to be legible
- expressive enough to feel text-first
- recoverable when stuck

### 4. Measurable progression
Progression must change capability, not just numbers.
If a gain does not unlock information, access, leverage, or consequence, it is not real progression.

### 5. Lanterns are systemic, not decorative
Lantern state must alter clue quality, witness confidence, access, movement, or legitimacy.

### 6. Missingness is selective and structured
It must create targeted instability, not random nonsense.

### 7. Mystery through partial truth, not unclear writing
The player may lack information, but the system and prose should remain legible.
If the player finds a clue before its related case is formally active, the game should frame that clue as noteworthy so the player knows it matters even if the meaning is not yet clear.

### 8. The city must remember
Case resolution must change persistent state in a visible way.

## Canonical MVP Source Set

If an implementer needs the minimum design pack, use this exact set first:
- `briefs/canonical-doc-index.md`
- `briefs/design-brief.md`
- `briefs/mvp-scope.md`
- `briefs/writing-bible.md`
- `mechanics/player-interaction-model.md`
- `mechanics/progression-thresholds-and-unlocks.md`
- `mechanics/lantern-and-missingness-rules.md`
- `cases/mvp-reference-case.md`
- `npcs/mvp-missing-clerk-cast.md`
- `districts/mvp-old-quarter.md`
- `districts/mvp-lantern-ward.md`
- `factions/mvp-memory-keepers.md`
- `factions/mvp-shrine-circles.md`
- `factions/mvp-council-of-lights.md`
- `backend/llm-interface-spec.md`
- `backend/prompt-contracts.md`
- `mechanics/request-lifecycle.md`
- `mechanics/json-object-model.md`
- `backend/storage-spec.md`

## Implementation Architecture Expectations

The MVP should be built around:
- Python 3.12
- FastAPI
- SQLite
- SQLAlchemy 2.x
- Pydantic v2
- httpx
- pytest
- ruff
- Hatchling
- `src/` layout
- console entry point: `lantern_city.cli:main`

### Architectural direction
Use a persistent world-state model with narrow active-slice loading.
Generate the city in layers:
- seed
- district
- location/scene
- NPC response
- clue update
- fallout

Cache summaries separately from source-of-truth objects.
Persist state after every meaningful action.

## Execution Method

Use subagent-driven execution.

### Operating mode
- one fresh implementer subagent per task
- spec compliance review first
- code quality review second
- do not move to the next task until both pass

### Canonical execution references
- `briefs/implementation-plan.md`
- `briefs/coding-agent-tasklist.md`
- `briefs/subagent-execution-plan.md`
- `briefs/world-turn-and-social-simulation-brief.md`

### Skill expectation
When actually executing code work, follow the logic of:
- `subagent-driven-development`

That means:
- tasks must be passed to subagents with full context
- subagents should not need to read the whole design archive
- each task should be narrow and reviewable

## Recommended Execution Order

At a high level, build in this order:

1. core models and serialization
2. storage layer and seed schema validation
3. LLM client abstraction and city seed generation
4. bootstrap and active-slice orchestration
5. district and location expansion tasks
6. NPC response generation
7. clue update logic
8. lantern and Missingness rule engine hooks
9. progression updates and unlock handling
10. case progression and fallout
11. caching and background precompute
12. minimal CLI loop and end-to-end playable path

## Immediate First Coding Slice

The safest first implementation slice is:
- runtime models
- serialization
- SQLite storage
- seed validation

Reason:
These establish the engine-owned state layer before any generation or gameplay glue is written.

## First End-to-End Target

The first real playable vertical slice should be:
- start new game
- load seed
- enter Old Quarter
- present Archive Steps scene
- talk to Sered Marr or inspect postings
- generate/update first clue
- persist state
- show updated next actions

That first clue may precede formal case activation, but the response must still signal that it is significant rather than dropping it with no framing.

This is a better early milestone than trying to build the whole case at once.

## Review Rules

Every implementation task should be reviewed against two standards.

### 1. Spec compliance review
Ask:
- does this match the design and task requirements exactly?
- are file paths and contracts correct?
- did the implementer add unsupported scope?

### 2. Code quality review
Ask:
- is the code clear, maintainable, and testable?
- does it fit project conventions?
- does it preserve engine-owned state and narrow generation boundaries?
- are tests meaningful?

### Rule
Spec review must pass before quality review matters.
Do not invert that order.

## Testing Expectations

The MVP should be built test-first where practical.
At minimum, the codebase should accumulate tests for:
- model validation
- serialization
- storage round-trips
- seed validation
- LLM output validation/repair
- lantern and Missingness rule application
- progression updates
- clue state transitions
- one or more end-to-end case-path tests at the orchestration layer

### Special caution
Because the LLM layer is constrained, many important tests should focus on:
- schema conformance
- state update correctness
- prompt-building boundaries
- repair behavior after malformed output

## Implementation Safety Rules

Do not:
- let the model invent persistent facts outside validated outputs
- hide unresolved design choices inside code defaults without documenting them
- expand the MVP case beyond the canonical authored content set during build
- create gameplay branches that contradict the interaction model
- treat lantern/Missingness effects as pure flavor when the rules say they are systemic
- use broad freeform prompting where a task contract exists

Do:
- keep state explicit
- keep context packets small
- cache summaries separately from durable truth
- expose player-facing consequences clearly
- let failure create new state rather than dead ends
- make meaningful clue discoveries legible, especially before the player fully understands what case they belong to

## Recommended Runtime Priorities

When forced to choose, prioritize in this order:

1. state correctness
2. rule correctness
3. interaction clarity
4. generation quality
5. prose polish

Why:
Lantern City can survive rough early prose.
It cannot survive broken state ownership or inconsistent clue/rule logic.

## Handoff Notes for Future Controller Agents

If you are the controller agent driving implementation:
- start from the canonical doc index
- give each subagent only the docs relevant to its task
- quote exact requirements into subagent context
- keep tasks file-bounded where possible
- run review loops rigorously
- avoid contaminating one task with unresolved assumptions from another

If you discover a design/document mismatch during implementation:
- patch the docs first or at least record the discrepancy clearly
- do not silently choose one interpretation in code without documenting it

## Suggested Initial Launch Prompt For Implementation Controller

A future implementation session can be launched with an instruction like:

```text
Implement Lantern City MVP from the canonical docs in /home/rich/lantern-city-docs.
Start with /home/rich/lantern-city-docs/briefs/canonical-doc-index.md and treat it as the navigation source of truth.
Use subagent-driven execution: one fresh implementation subagent per task, followed by spec review and code quality review before moving on.
Begin with the first coding slice: models, serialization, SQLite storage, and seed validation.
Preserve engine-owned state, narrow generation, and the authored MVP case structure.
```

## Readiness Assessment

Lantern City is ready for implementation planning and controlled build execution.
It is not “fully content-complete” for the entire future game, but it is sufficiently specified for:
- MVP architecture work
- MVP vertical slice work
- subagent-driven coding execution
- structured review and verification

## Summary

This handoff marks the transition from design-first work to build-first work.
The design set is now strong enough that implementation should focus on faithful execution, not invention.

Use:
- `briefs/canonical-doc-index.md` for navigation
- the canonical MVP source set for design truth
- the implementation plan and subagent execution plan for build order
- two-stage review for every task

If this process is followed, Lantern City should enter implementation with a much lower risk of design drift or architecture confusion.
