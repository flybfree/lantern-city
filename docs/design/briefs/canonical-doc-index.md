# Lantern City — Canonical Document Index

## Purpose

This document is the navigation point for the current Lantern City source-of-truth docs.
It exists to reduce ambiguity now that the workspace contains:
- early design docs
- deeper system docs
- reference content docs
- implementation-facing backend docs
- historical notes and handoff materials

If a future implementation pass needs to know which document to trust first, start here.

## How To Use This Index

Use the documents listed here as the current authoritative references by topic.
If another document disagrees with one listed here, prefer the canonical document named in this index.

## 1. Project Identity and Core Vision

### Primary source
- `briefs/design-brief.md`

### Use this for
- high concept
- tone and mood
- player fantasy
- core loop
- district and faction top-line identity
- the overall “what is Lantern City?” question

## 2. MVP Scope

### Primary source
- `briefs/mvp-scope.md`

### Use this for
- what the first playable version must include
- what the MVP deliberately excludes
- build-order priorities at the product level

## 3. Current Design Gap / Cleanup Status

### Primary sources
- `briefs/design-gaps-audit.md`
- `briefs/design-consistency-audit.md`

### Use these for
- what used to be missing
- what was later filled in
- known normalization issues and cleanup history

### Important note
These are audit docs, not gameplay source-of-truth docs.
Use them to understand status and maintenance needs, not to define runtime behavior.

## 4. Writing and Tone Standards

### Primary source
- `briefs/writing-bible.md`

### Use this for
- prose style
- dialogue style
- clue-writing style
- summary-writing style
- cliché avoidance
- generation tone guardrails

If any generated or authored text drifts stylistically, correct it against this document.

## 5. Player Experience and Interaction Model

### Primary source
- `mechanics/player-interaction-model.md`

### Use this for
- what the player sees each turn
- how actions are presented
- structured actions vs guided free text
- case board and journal behavior
- stuck-state recovery UX
- scene interaction grammar

## 6. Core Mechanics and World-State Logic

### Primary supporting sources
- `mechanics/core-mechanics.md`
- `mechanics/case-structure.md`
- `mechanics/scene-structure.md`
- `mechanics/npc-interaction-system.md`
- `mechanics/npc-progression-integration.md`

### Use these for
- overall mechanic intent
- case and scene definitions
- conversation relevance design
- how social interaction feeds progression

## 7. Progression System

### Canonical source
- `mechanics/progression-thresholds-and-unlocks.md`

### Supporting background sources
- `mechanics/progression-system-spec.md`
- `mechanics/progression-tracks.md`

### Use the canonical source for
- track labels
- thresholds
- unlock tables
- gain/loss pacing
- cross-track interactions
- per-scene and per-case tuning

### Important note
If there is any disagreement between progression docs, use:
- `mechanics/progression-thresholds-and-unlocks.md`
as the source of truth.

## 8. Lantern and Missingness Rules

### Canonical source
- `mechanics/lantern-and-missingness-rules.md`

### Supporting background source
- `mechanics/lanterns.md`

### Use the canonical source for
- lantern state effects
- witness confidence rules
- clue reliability behavior
- route and access effects
- Missingness pressure levels
- propagation rules
- stabilization vs restoration vs permanent loss

### Important note
If there is any disagreement between lantern docs, use:
- `mechanics/lantern-and-missingness-rules.md`
as the operational source of truth.

## 9. MVP Reference Content

### Canonical source
- `cases/mvp-reference-case.md`

### Use this for
- the first playable case
- clue web
- route structure
- resolution paths
- fallout patterns
- the canonical MVP social and investigative arc

## 10. MVP NPC Cast

### Canonical source
- `npcs/mvp-missing-clerk-cast.md`

### Use this for
- named NPC sheets
- motives
- hidden information
- trust triggers
- pressure reactions
- clue links
- escalation logic

## 11. MVP Districts

### Canonical sources
- `districts/mvp-old-quarter.md`
- `districts/mvp-lantern-ward.md`

### Use these for
- district identity
- local economy and social rules
- location sets
- movement and access patterns
- district-specific gameplay pressure
- district-level fallout behavior

## 12. MVP Factions

### Canonical sources
- `factions/mvp-memory-keepers.md`
- `factions/mvp-shrine-circles.md`
- `factions/mvp-council-of-lights.md`

### Use these for
- faction goals
- methods
- assets
- red lines
- relations with each other
- case-specific reaction logic

## 13. Backend LLM / Generation Contracts

### Canonical sources
- `backend/llm-interface-spec.md`
- `backend/prompt-contracts.md`

### Use these for
- task types
- request/response contract shape
- prompt rules
- validation and repair guidance
- generation task scope boundaries

### Important note
Use `backend/prompt-contracts.md` as the task-behavior source of truth.
Use `backend/llm-interface-spec.md` as the abstraction/interface source of truth.

## 14. Backend Data and Seed Structure

### Canonical sources
- `backend/city-seed-schema.md`
- `mechanics/json-object-model.md`
- `backend/storage-spec.md`
- `backend/state-orchestration.md`

### Use these for
- seed schema
- runtime object shape
- persistence direction
- orchestration flow and state loading behavior

## 15. Request Flow and Runtime Slice Rules

### Canonical sources
- `mechanics/request-lifecycle.md`
- `backend/state-orchestration.md`
- `backend/backend-overview.md`

### Use these for
- narrow request handling
- active-slice loading
- generator call timing
- persistence and cache interactions

## 16. Implementation Planning and Handoff

### Primary references
- `briefs/implementation-plan.md`
- `briefs/coding-agent-tasklist.md`
- `briefs/subagent-execution-plan.md`
- `briefs/post-mvp-execution-roadmap.md`

### Use these for
- implementation sequencing
- coding task decomposition
- subagent-driven execution planning
- post-MVP depth and simulation work

### Important note
These are planning and handoff docs.
When implementation details conflict with newer design docs, the newer canonical design docs should win.

## 17. Docs That Are Useful but Not Primary Source-of-Truth

These are still useful, but should be treated as secondary or historical unless explicitly promoted.

### Secondary / background docs
- `mechanics/overview.md`
- `mechanics/implementation-spec.md`
- `mechanics/lazy-generation-pipeline.md`
- `mechanics/generation-and-token-budgeting.md`
- `mechanics/sequence-diagrams.md`
- `backend/api-contract.md`
- `backend/dependency-plan.md`
- `backend/project-structure.md`

### Historical / transitional docs
- session resume notes
- launch pack notes
- repo bootstrap checklists
- draft pyproject docs where a final exists

These can still be valuable, but they should not override the canonical docs listed earlier.

## 18. Recommended Reading Order For A New Implementer

If someone is joining the project fresh, read in this order:

1. `briefs/design-brief.md`
2. `briefs/mvp-scope.md`
3. `briefs/writing-bible.md`
4. `mechanics/player-interaction-model.md`
5. `cases/mvp-reference-case.md`
6. `npcs/mvp-missing-clerk-cast.md`
7. `districts/mvp-old-quarter.md`
8. `districts/mvp-lantern-ward.md`
9. `factions/mvp-memory-keepers.md`
10. `factions/mvp-shrine-circles.md`
11. `factions/mvp-council-of-lights.md`
12. `mechanics/progression-thresholds-and-unlocks.md`
13. `mechanics/lantern-and-missingness-rules.md`
14. `backend/llm-interface-spec.md`
15. `backend/prompt-contracts.md`
16. `mechanics/request-lifecycle.md`
17. `mechanics/json-object-model.md`
18. `backend/storage-spec.md`
19. `briefs/implementation-plan.md`
20. `briefs/coding-agent-tasklist.md`

## 19. Current Canonical MVP Spine

If only a minimal implementation spine is needed, use this exact set:
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

## Summary

This index marks the current Lantern City source-of-truth doc set.
Use it as the first stop before implementation, review, or future design expansion.

If the workspace continues to grow, update this file whenever a new document becomes canonical.
