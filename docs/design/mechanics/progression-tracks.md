# Lantern City — Progression Tracks

## Purpose

These tracks make player progression measurable in-game.
They should reflect real increases in capability, not just abstract leveling.

The player should feel progression as:
- seeing more
- going more places
- changing more outcomes
- understanding the city more deeply

## Core Tracks

### 1. Lantern Understanding
Measures how well the player understands how lanterns work.

What it affects:
- ability to interpret lantern states
- ability to detect tampering or ritual alteration
- ability to estimate lantern reach and influence
- access to advanced lantern-related actions

How it increases:
- observing lantern behavior
- comparing districts
- interrogating experts
- inspecting lantern hardware or records
- seeing cause-and-effect after lantern changes

Example thresholds:
- Novice: knows lanterns matter
- Informed: knows lanterns affect districts and testimony
- Literate: can identify control, reach, and manipulation
- Expert: can predict lantern effects
- Deep Expert: can exploit or reverse lantern systems

### 2. Access
Measures where the player can physically or socially enter.

What it affects:
- district entry
- private meetings
- archives
- ritual spaces
- faction backrooms
- secret routes such as the Underways

How it increases:
- earning trust
- completing favors
- gaining credentials
- building reputation
- uncovering useful secrets

Example thresholds:
- Public access only
- Restricted access to specific locations
- Faction access in some districts
- Broad citywide access
- Hidden or secret access routes unlocked

### 3. Reputation
Measures how groups and districts perceive the player.

Track reputation separately for:
- major factions
- major districts
- key social circles if needed

What it affects:
- whether people talk to the player
- whether they are helped or blocked
- whether they are trusted, feared, or ignored
- whether officials and NPCs treat them as legitimate

How it increases:
- helping people
- solving problems
- honoring commitments
- surviving public scrutiny
- aligning with local interests

How it decreases:
- breaking promises
- exposing sensitive secrets
- siding against a faction
- causing public harm
- being caught in a lie

### 4. Leverage
Measures the player’s ability to pressure outcomes.

What it affects:
- forcing cooperation
- extracting meetings
- changing testimony
- preventing a hostile action
- bargaining with factions

What counts as leverage:
- secrets
- debts
- favors
- proof
- social standing
- ritual authority
- trade pressure

How it increases:
- finding contradictions
- discovering hidden motives
- completing favors that can be called in later
- earning debt from NPCs or factions
- acquiring sensitive evidence

### 5. City Impact
Measures how much the city reacts to the player.

This is not just power. It is visibility and consequence.

What it affects:
- whether NPCs adjust plans because of the player
- whether faction leaders notice the player
- whether lantern systems shift in response to their actions
- whether the player can meaningfully redirect events

How it increases:
- solving larger cases
- interfering with faction plans
- changing district stability
- revealing hidden systems
- becoming a known force in the city

### 6. Clue Mastery
Measures how well the player handles information.

What it affects:
- ability to sort reliable from unreliable evidence
- ability to connect clues across scenes
- ability to recognize missing information
- ability to identify when the city is lying through omission

How it increases:
- careful observation
- comparing witness reports
- reviewing records
- testing hypotheses
- successfully resolving mysteries

## Supporting State Tracks

These are not player progression tracks in the same sense, but they should be visible or legible because they shape play.

### District Stability
How coherent and safe a district feels.

### Missingness Pressure
How active the setting’s core anomaly is in a location or case.

### Faction Tension
How close groups are to open conflict.

### Civic Trust
How much the city’s institutions are believed.

These tracks should change because of the player, but they are also broader world state.

## Recommended UI Model

The game does not need to expose raw numbers for everything.
A good approach is:
- show rank or tier for major tracks
- show progress bars only where helpful
- reveal exact values only in developer/debug or advanced mode
- allow players to infer hidden state from behavior and consequences

Suggested visible labels:
- Lantern Understanding: Untrained / Informed / Literate / Expert / Deep Expert
- Access: Public / Restricted / Trusted / Cleared / Secret
- Reputation: Wary / Known / Respected / Trusted / Established
- Leverage: None / Limited / Useful / Strong / Dominant
- City Impact: Minimal / Local / District / Citywide / Structural
- Clue Mastery: Basic / Competent / Sharp / Insightful / Forensic

Canonical note:
- The authoritative threshold, label, pacing, and unlock definitions now live in `mechanics/progression-thresholds-and-unlocks.md`.
- If this file and that file ever diverge, use `mechanics/progression-thresholds-and-unlocks.md` as the source of truth.

## Design Rule

Progress should always unlock one of these:
- more information
- more access
- more influence
- more nuance
- more consequences

If a progression gain does not change gameplay, it is not a real track.

## Best Practice

The player should feel progression in the story, but the system should also measure it clearly.
That means the subjective feeling and the objective mechanics should match.

When the player says:
- “I can see more”
- “I can go more places”
- “I can change more”

The game should be able to point to a track that explains why.
