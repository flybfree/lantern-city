# Lantern City — Design Consistency Audit

## Purpose

This document records the results of a consistency pass across the current Lantern City design set.
It focuses on:
- cross-document terminology drift
- stale assumptions that are no longer true
- mismatched labels or thresholds
- places where the design is coherent but duplicated
- recommended cleanup actions before implementation handoff

This is not a critique of the design quality.
The overall design is now strong.
This audit is about reducing ambiguity before build execution.

## Overall Assessment

Lantern City’s design set is now broadly coherent.
The core design spine is in place and the newer documents line up well around:
- the MVP reference case
- the two MVP districts
- the MVP faction set
- the NPC cast
- progression as measurable capability
- lantern and Missingness rules
- engine-owned generation constraints
- writing standards

Most remaining issues are not structural design gaps.
They are document-maintenance issues:
- terminology drift
- older documents superseded by newer ones
- placeholder assumptions that are now outdated
- a few label mismatches that should be normalized

## High-Priority Consistency Issues

## 1. Progression labels drift across documents

### What is happening
There are now multiple versions of visible track labels across older and newer docs.

Examples:
- `mechanics/progression-tracks.md` uses:
  - Lantern Understanding: Novice / Informed / Literate / Expert / Deep Expert
  - Access: Public / Restricted / Trusted / Cleared / Secret
  - Reputation: Friendly / Neutral / Wary / Hostile / Loyal
  - Leverage: None / Limited / Useful / Strong / Dominant
  - City Impact: Local / District / Citywide / Structural
- `mechanics/progression-system-spec.md` uses examples like:
  - Access: Restricted
  - Reputation: Wary
  - Leverage: Limited
  - City Impact: Local
  - Clue Mastery: Competent
- `mechanics/progression-thresholds-and-unlocks.md` now defines the most operational label set:
  - Lantern Understanding: Untrained / Informed / Literate / Expert / Deep Expert
  - Access: Public / Restricted / Trusted / Cleared / Secret
  - Reputation: Wary / Known / Respected / Trusted / Established
  - Leverage: None / Limited / Useful / Strong / Dominant
  - City Impact: Minimal / Local / District / Citywide / Structural
  - Clue Mastery: Basic / Competent / Sharp / Insightful / Forensic

### Why it matters
The newer thresholds doc is clearly the authoritative tuning layer now, but older docs still imply other label sets.
That can create implementation ambiguity and UI mismatch.

### Recommendation
Promote `mechanics/progression-thresholds-and-unlocks.md` as the canonical source for track labels and thresholds.
Then patch older docs so they either:
- match those labels
or
- explicitly defer to the thresholds doc

### Priority
High

## 2. Design gaps audit now contains stale statements

### What is happening
`briefs/design-gaps-audit.md` still says:
- the `districts/` folder currently contains only a README placeholder
- the `factions/` folder currently contains only a README placeholder
- the `npcs/` folder currently contains only a README placeholder

Those statements are no longer true.

### Why it matters
The audit remains useful historically, but it is now partly stale as a current-state document.
Someone resuming work later could misread it as the present situation.

### Recommendation
Patch the audit so it either:
- marks those items as resolved
or
- adds a top note saying this was the gap state before later docs were written

### Priority
High

## 3. Case-related location naming varies slightly across docs

### What is happening
The same late-case space is described with slightly different names, including:
- Hidden side chamber / subarchive recess
- Hidden Chamber
- subarchive recess

Likewise the hidden route space is described with variants such as:
- Maintenance Passage / Lamp Access Crawl
- Service Passage / Lamp Access Crawl
- hidden route

### Why it matters
This is not a design contradiction, but it is enough naming drift to create confusion in implementation, state IDs, and task decomposition.

### Recommendation
Choose one canonical public-facing location name and one canonical internal ID set.
For example:
- public names:
  - Service Passage
  - Subarchive Chamber
- internal IDs:
  - `location_service_passage`
  - `location_subarchive_chamber`

Then patch the case, district, and object-model examples to match.

### Priority
High

## Medium-Priority Consistency Issues

## 4. Lantern Ward scope is intentionally smaller than Old Quarter, but some docs still describe it a bit broadly

### What is happening
The newer Lantern Ward district doc is consistent internally: it is a support district, not a full exploration district.
But the reference case and some broader district descriptions still allow it to read as either:
- a full secondary district
or
- a narrower administrative edge support space

### Why it matters
This is not broken, but it could affect implementation effort if not made explicit.

### Recommendation
Keep the newer district doc as authoritative.
In implementation-facing docs, describe Lantern Ward as:
- a compact secondary MVP district with 3 to 4 critical locations
- not a second large exploration district in the first build

### Priority
Medium

## 5. Reputation is defined both globally and by faction/district in different places

### What is happening
Some docs speak about Reputation as one player track.
Others say reputation should be tracked separately by faction and district.
The newer progression thresholds doc says:
- use one general label plus optional faction/district modifiers for the MVP

### Why it matters
This is a design decision that is actually mostly resolved, but older documents still imply a more fragmented system.

### Recommendation
Normalize the MVP decision as:
- one global Reputation progression track for capability progression
- optional faction/district reputation modifiers as supporting state, not separate full progression tracks

This preserves both simplicity and social nuance.

### Priority
Medium

## 6. Access sometimes reads as a pure progression score and sometimes as strongly contextual permission

### What is happening
This is mostly intentional, but some docs read as if Access alone unlocks rooms, while newer docs correctly say major unlocks should require both:
- a track threshold
and
- a narrative condition

### Why it matters
Without a clear hierarchy, implementation might incorrectly reduce access to a raw stat gate.

### Recommendation
Treat `mechanics/progression-thresholds-and-unlocks.md` as the authoritative interpretation:
- Access score enables categories of access
- actual entry still depends on trust, evidence, invitation, route knowledge, or local state

### Priority
Medium

## 7. Some implementation-facing docs still reference older draft artifacts

### What is happening
Search results show several docs still refer to drafts, placeholders, and setup artifacts such as:
- `pyproject-toml-draft.md`
- `gitignore-draft.txt`
- draft setup notes
- “placeholder” wording in some backend docs

### Why it matters
This is normal in a living doc set, but it means the workspace now has both design-truth and historical handoff material mixed together.

### Recommendation
Before coding starts, separate docs into:
- authoritative current docs
- archived drafts / historical notes

Or add “status” headers to docs such as:
- current
- superseded
- historical reference

### Priority
Medium

## Lower-Priority Issues

## 8. The JSON object model examples are still illustrative and do not yet fully reflect the new named MVP content set

### What is happening
The object model is still generally aligned, but it uses older illustrative fragments and not the full newer canonical naming set from the reference case and district docs.

### Why it matters
This is not a contradiction, but it means implementation could benefit from updated canonical example payloads.

### Recommendation
Later, patch `mechanics/json-object-model.md` so its examples use the final chosen MVP IDs and public names consistently.

### Priority
Low

## 9. Some docs still speak of “Lantern Ward or administrative edge site”

### What is happening
That phrasing made sense before the Lantern Ward district was fully authored.
Now that `districts/mvp-lantern-ward.md` exists, that ambiguity is less necessary.

### Why it matters
Minor only, but the case doc should now probably commit to Lantern Ward as the canonical secondary district.

### Recommendation
Patch `cases/mvp-reference-case.md` to prefer Lantern Ward explicitly for the MVP.

### Priority
Low

## 10. Some docs contain historical scaffolding that is now less useful for day-to-day navigation

### What is happening
There are several “session resume,” “launch pack,” “handoff,” and bootstrap docs that may be helpful historically but are no longer the clearest place to find truth.

### Why it matters
A future implementation pass may waste time figuring out which brief is the real source.

### Recommendation
Create a short “authoritative docs index” pointing to the current canonical docs by topic.

### Priority
Low

## Canonical Sources Recommended After This Audit

If no cleanup is done, these should still be treated as the practical current source of truth.

### Core concept and tone
- `briefs/design-brief.md`
- `briefs/writing-bible.md`

### MVP definition
- `briefs/mvp-scope.md`
- `cases/mvp-reference-case.md`

### Interaction
- `mechanics/player-interaction-model.md`

### Progression
- `mechanics/progression-thresholds-and-unlocks.md`

### Lantern / Missingness behavior
- `mechanics/lantern-and-missingness-rules.md`

### Districts
- `districts/mvp-old-quarter.md`
- `districts/mvp-lantern-ward.md`

### NPCs
- `npcs/mvp-missing-clerk-cast.md`

### Factions
- `factions/mvp-memory-keepers.md`
- `factions/mvp-shrine-circles.md`
- `factions/mvp-council-of-lights.md`

### Generation
- `backend/llm-interface-spec.md`
- `backend/prompt-contracts.md`

## Recommended Cleanup Order

1. Normalize progression labels across progression docs
2. Patch stale statements in `design-gaps-audit.md`
3. Normalize canonical location names and IDs for the hidden route/chamber spaces
4. Patch case doc to commit to Lantern Ward as the MVP secondary district
5. Mark draft/historical backend docs more clearly as draft or superseded
6. Optionally refresh the JSON object model examples to match the finalized MVP content set

## Summary

Lantern City’s design is now broadly consistent and implementation-oriented.
The remaining issues are mostly maintenance and normalization issues, not conceptual ones.

The highest-value cleanup items are:
- progression label normalization
- stale audit cleanup
- canonical location naming
- explicit MVP commitment to Lantern Ward as the secondary district

Once those are resolved, the doc set will be significantly easier to hand off into implementation without ambiguity.