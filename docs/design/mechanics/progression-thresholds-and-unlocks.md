# Lantern City — Progression Thresholds and Unlock Tables

## Purpose

This document makes Lantern City’s progression system operational.
It turns the existing track concepts into concrete MVP rules for:
- score ranges
- tier boundaries
- unlock tables
- gain sizes
- loss rules
- cross-track interactions
- pacing targets for scenes and cases

This document should be read as the tuning layer that sits on top of:
- `mechanics/progression-tracks.md`
- `mechanics/progression-system-spec.md`
- `mechanics/npc-progression-integration.md`

## Design Goal

The player should be able to feel progression as real changes in capability.
That means every track needs to answer:
- what raises it
- when it changes tier
- what the new tier actually unlocks
- how quickly it should move in the MVP

If a track changes but play does not, the track is too abstract.

## Core Progression Model

For the MVP, all six main tracks should use:
- a 0 to 100 score range
- five tiers
- hidden exact values by default
- visible tier labels in normal play
- optional exact-score display in debug or advanced mode

## Tier Boundaries

Use the same numeric thresholds for all six core tracks.

- Tier 1: 0 to 19
- Tier 2: 20 to 39
- Tier 3: 40 to 59
- Tier 4: 60 to 79
- Tier 5: 80 to 100

This keeps the system legible while still allowing different unlock tables per track.

## MVP Starting Values

Use these as default starting values for the MVP reference case.
These align with the existing seed examples and keep the player competent but limited.

- Lantern Understanding: 18
- Access: 10
- Reputation: 12
- Leverage: 5
- City Impact: 2
- Clue Mastery: 20

### Starting tier interpretation
- Lantern Understanding: Tier 1, almost Tier 2
- Access: Tier 1
- Reputation: Tier 1
- Leverage: Tier 1
- City Impact: Tier 1
- Clue Mastery: Tier 2

### Why these starts work
The player should begin the MVP as:
- observant enough to notice oddity
- not yet trusted by institutions
- not yet powerful socially
- slightly more capable of reading clues than the average citizen

This fits the fantasy of a fixer-investigator entering a live city rather than a total novice or a city master.

## Track Labels by Tier

These are the recommended visible labels in normal UI.

### 1. Lantern Understanding
- Tier 1: Untrained
- Tier 2: Informed
- Tier 3: Literate
- Tier 4: Expert
- Tier 5: Deep Expert

### 2. Access
- Tier 1: Public
- Tier 2: Restricted
- Tier 3: Trusted
- Tier 4: Cleared
- Tier 5: Secret

### 3. Reputation
For the MVP, use one general label plus optional faction/district modifiers.
- Tier 1: Wary
- Tier 2: Known
- Tier 3: Respected
- Tier 4: Trusted
- Tier 5: Established

### 4. Leverage
- Tier 1: None
- Tier 2: Limited
- Tier 3: Useful
- Tier 4: Strong
- Tier 5: Dominant

### 5. City Impact
- Tier 1: Minimal
- Tier 2: Local
- Tier 3: District
- Tier 4: Citywide
- Tier 5: Structural

### 6. Clue Mastery
- Tier 1: Basic
- Tier 2: Competent
- Tier 3: Sharp
- Tier 4: Insightful
- Tier 5: Forensic

## Gain Size Rules

Use four main gain sizes in the MVP.

### Tiny gain: 1 to 2 points
Use for:
- confirming a minor suspicion
- getting a small useful reaction from a world NPC
- spotting a weak but valid clue signal

### Small gain: 3 to 5 points
Use for:
- a meaningful but local discovery
- a new route hint
- a trust-positive conversation turn with a relevant NPC
- identifying a contradiction with partial confidence

### Medium gain: 6 to 10 points
Use for:
- opening a restricted location
- securing a named lead
- proving a clue is more reliable than it first appeared
- gaining a favor, debt, or formal acknowledgement

### Large gain: 11 to 18 points
Use for:
- a case-defining clue
- major access breakthrough
- strong leverage over an important NPC or institution
- a resolution choice with visible district consequence

### Exceptional gain: 19 to 25 points
Use sparingly.
Only for:
- solving the case cleanly
- exposing a major systemic truth
- permanently altering a district-level relationship to the player

## Loss and Decay Rules

The MVP should include limited loss rules, but not aggressive decay.
The player should not feel punished for progress they already earned.

### No passive decay
None of the six main tracks should decay over time simply because time passed.

### Situational losses are allowed
A track may drop when the player causes a meaningful setback.

#### Recommended loss sizes
- small setback: -2 to -5
- serious setback: -6 to -10
- major public failure: -11 to -15

### Best use of losses by track
- Reputation: most likely to fall
- Leverage: can be lost if evidence becomes invalid, exposed, or spent
- Access: can be revoked or narrowed
- City Impact: should rarely fall, but can stall
- Lantern Understanding and Clue Mastery: should almost never fall unless a system explicitly supports misinformation or false learning

### MVP rule
For the MVP reference case, prefer:
- losses to Reputation, Access, and Leverage
- not losses to Lantern Understanding or Clue Mastery

This keeps learning progress stable while still allowing social and political consequences.

## Cross-Track Interaction Rules

The tracks should not be fully independent.
The game is stronger when progress in one area creates opportunities in another.

### Lantern Understanding -> Clue Mastery
At Tier 2 or higher in Lantern Understanding:
- the player can reinterpret some clue states more accurately
- some lantern-linked contradictions become easier to surface

### Clue Mastery -> Leverage
At Tier 2 or higher in Clue Mastery:
- connecting contradiction chains can convert clues into leverage more efficiently

### Reputation -> Access
At Tier 2 or higher in district or faction reputation:
- NPCs are more willing to grant informal access
- some restricted spaces require less direct leverage

### Access -> City Impact
At Tier 3 or higher in Access:
- the player reaches spaces where decisions have wider consequences
- this makes City Impact gains more available

### Leverage -> Access or Resolution Quality
At Tier 2 or higher in Leverage:
- blocked conversations can reopen
- political or negotiated endings become more viable

### City Impact -> Reputation Sensitivity
At higher City Impact:
- public decisions matter more
- failures also spread farther

## Unlock Philosophy

Unlocks should come in four types:
- interpretation unlocks
- location/access unlocks
- social influence unlocks
- resolution-quality unlocks

The player should feel each tier as a change in:
- what they notice
- where they can go
- who will talk to them
- what endings they can force or negotiate

## Lantern Understanding Unlock Table

### Tier 1: Untrained (0 to 19)
The player can:
- tell when a lantern feels wrong only in broad atmospheric terms
- notice obvious light anomalies if surfaced by the scene

The player cannot reliably:
- distinguish neglect from manipulation
- estimate reach or interpret contradiction as lantern-linked

### Tier 2: Informed (20 to 39)
Unlocks:
- identify that a lantern problem may be deliberate rather than accidental
- ask better lantern-specific questions in conversation
- receive clearer clue notes for lantern-linked evidence

MVP examples:
- “This pattern does not look like simple neglect.”
- unlock action: Ask whether the outage began before the disappearance

### Tier 3: Literate (40 to 59)
Unlocks:
- distinguish common damage from probable alteration
- interpret whether unstable testimony may be location-linked
- infer rough lantern reach in a local area

MVP examples:
- unlock action: Compare witness reliability by location
- unlock clue upgrade: clue marked “uncertain” becomes “likely lantern-distorted”

### Tier 4: Expert (60 to 79)
Unlocks:
- predict likely social or memory effects from lantern condition
- identify more advanced alteration signatures
- propose stabilization-first interventions with better confidence

MVP note:
- unlikely to be reached in one-case MVP unless the player gains unusually heavily

### Tier 5: Deep Expert (80 to 100)
Unlocks:
- attempt deliberate reversal, exploitation, or controlled manipulation of lantern-linked systems
- read deeper systemic intent from localized anomalies

MVP note:
- this tier mostly exists for future-proofing, not routine MVP play

## Access Unlock Table

### Tier 1: Public (0 to 19)
The player can:
- enter public district spaces
- speak to publicly available NPCs
- inspect obvious scene elements

Cannot reliably access:
- private workrooms
- restricted records
- hidden service routes

### Tier 2: Restricted (20 to 39)
Unlocks:
- entry to selected restricted interiors
- one-step introductions or limited escorted access
- ability to revisit a guarded space with permission

MVP examples:
- shrine workroom
- partial archive desk review

### Tier 3: Trusted (40 to 59)
Unlocks:
- repeated access to key restricted spaces
- private meetings with mid-tier faction representatives
- access that persists beyond a single scene

MVP examples:
- ledger room access without immediate removal
- invitation to a more serious conversation with Sister Calis

### Tier 4: Cleared (60 to 79)
Unlocks:
- broad interior access across a faction’s relevant local spaces
- multiple institutional doors open without separate persuasion
- fewer blockers during investigative movement

### Tier 5: Secret (80 to 100)
Unlocks:
- hidden routes, protected archives, or off-ledger spaces
- access to places the public is not meant to know exist

MVP note:
- hidden-route access in the reference case can either require Tier 2/3 Access plus clue conditions, or be granted through special evidence even if raw Access remains lower

## Reputation Unlock Table

### Tier 1: Wary (0 to 19)
The player is:
- tolerated
- watched
- not fully trusted

Effects:
- NPCs offer only surface cooperation
- some conversations stay formal or guarded

### Tier 2: Known (20 to 39)
Unlocks:
- NPCs remember the player as a meaningful actor
- more willing redirection and named leads
- fewer reflexive dismissals

MVP examples:
- workers are willing to say “ask Ila” or “speak to Brin” instead of denying knowledge

### Tier 3: Respected (40 to 59)
Unlocks:
- more candid conversation openings
- easier goodwill-based access
- reduced social friction in a district or faction sphere

MVP examples:
- a local authority gives access because the player has handled matters carefully so far

### Tier 4: Trusted (60 to 79)
Unlocks:
- private disclosures without immediate leverage use
- more protective reactions from NPC allies
- some faction actors volunteer risk-bearing help

### Tier 5: Established (80 to 100)
Unlocks:
- the player’s name carries real prior weight
- public moves can reshape outcomes without constant proof repetition

MVP note:
- likely not reached broadly in one case, but useful later

## Leverage Unlock Table

### Tier 1: None (0 to 19)
The player can:
- ask
n- suggest
- imply

But cannot reliably:
- force cooperation
- reopen blocked lines
- bargain from strength

### Tier 2: Limited (20 to 39)
Unlocks:
- reopen a blocked discussion
- secure one concession from a compromised NPC
- make an official denial harder to maintain

MVP examples:
- pressure Sered with a missing maintenance line
- get Brin to admit an off-schedule route existed

### Tier 3: Useful (40 to 59)
Unlocks:
- force a meeting or private hearing
- negotiate with institutions from a non-trivial position
- change which endings are politically viable

MVP examples:
- compel a cleaner audience in Lantern Ward
- secure a political bargain instead of accepting dismissal

### Tier 4: Strong (60 to 79)
Unlocks:
- push multiple actors at once
- trade silence, exposure, or proof among factions
- redirect faction behavior decisively in a district-scale issue

### Tier 5: Dominant (80 to 100)
Unlocks:
- shape major outcomes even against strong resistance
- turn secrets into structural influence

MVP note:
- future-facing more than expected in the first case

## City Impact Unlock Table

### Tier 1: Minimal (0 to 19)
The player matters only locally and temporarily.

Effects:
- scenes change
- some NPCs remember
- the city does not yet broadly react

### Tier 2: Local (20 to 39)
Unlocks:
- district actors begin adjusting behavior because of the player
- rumors and small authority responses spread

MVP examples:
- the Old Quarter starts whispering about the player’s involvement
- Watcher Pell or a higher authority notices the case sooner because of the player’s actions

### Tier 3: District (40 to 59)
Unlocks:
- district state visibly shifts in response to the player
- faction posture adjusts in a sustained way
- case fallout becomes legible beyond one room or NPC

MVP examples:
- records confidence and public mood update across the district after resolution

### Tier 4: Citywide (60 to 79)
Unlocks:
- multiple districts or top-tier factions respond to player activity

### Tier 5: Structural (80 to 100)
Unlocks:
- the player can drive deep institutional change

MVP note:
- the first case may move City Impact from Tier 1 to Tier 2, and possibly Tier 3 on a very strong public resolution

## Clue Mastery Unlock Table

### Tier 1: Basic (0 to 19)
The player can:
- collect clues
- recognize obvious relevance

But struggles to:
- classify contradiction quality
- connect indirect patterns confidently

### Tier 2: Competent (20 to 39)
Unlocks:
- compare two clue sources more reliably
- recognize when a clue is incomplete rather than false
- ask more targeted follow-up questions

MVP examples:
- compare postings against roster copies
- notice the difference between missing data and contradictory data

### Tier 3: Sharp (40 to 59)
Unlocks:
- connect multi-scene clue chains
- identify omission as a clue class
- infer where to test a theory next

MVP examples:
- connect outage timing, missing line, and witness instability into a coherent next step

### Tier 4: Insightful (60 to 79)
Unlocks:
- better confidence filtering under uncertainty
- stronger clue summaries and contradiction mapping
- lower chance of pursuing dead-end interpretations

### Tier 5: Forensic (80 to 100)
Unlocks:
- near-expert inference across layered unreliable evidence
- highly efficient identification of hidden pattern structures

MVP note:
- Tier 3 is a good upper target for the first case

## Track-Specific Loss Rules

### Lantern Understanding
- usually no losses in MVP
- false theories should waste time, not erase knowledge

### Access
Can fall when:
- the player is expelled from a space
- a faction revokes trust
- a public scene hardens restrictions

### Reputation
Can fall when:
- the player breaks promises
- blames the wrong party loudly
- mishandles a public truth
- chooses a resolution that harms one group’s standing

### Leverage
Can fall when:
- a secret is spent
- evidence is exposed and no longer privately useful
- the player trades it away in a bargain

### City Impact
Usually does not fall directly in MVP.
A failed ending can instead harden future responses, which is a different kind of consequence.

### Clue Mastery
Usually no direct losses in MVP.
Misreading clues should create bad choices, not stat punishment.

## Per-Scene Progression Targets

A normal meaningful scene should usually move:
- 1 primary track by 3 to 8 points
- optionally 1 secondary track by 1 to 4 points

A major breakthrough scene may move:
- 1 to 2 tracks by 8 to 15 points each

A filler or flavor scene should move:
- no track
or
- at most 1 to 2 points if it truly improves social context or clue confidence

## Per-Case Progression Targets for The Missing Clerk

For a normal playthrough of the MVP reference case, a good expected range is:

- Lantern Understanding: +10 to +25
- Access: +10 to +25
- Reputation: +5 to +20 depending on choices
- Leverage: +10 to +30 depending on evidence use
- City Impact: +5 to +20 depending on resolution route
- Clue Mastery: +12 to +25

### Likely end-state targets for a strong but not perfect run
- Lantern Understanding: Tier 2, approaching Tier 3
- Access: Tier 2, possibly Tier 3
- Reputation: Tier 2
- Leverage: Tier 2 or Tier 3
- City Impact: Tier 2
- Clue Mastery: Tier 2 or Tier 3

### Why this pacing works
The first case should show meaningful growth without making the player feel finished.
They should end the MVP clearly stronger than they began, but still with much more city to learn.

## Example MVP Gain Mapping

### Archive Steps opening scene
Possible gains:
- Clue Mastery +3 for spotting contradiction in postings
- Reputation +2 if the player handles Sered carefully

### First good conversation with Ila Venn
Possible gains:
- Lantern Understanding +5
- Clue Mastery +3

### Inspecting the lantern bracket successfully
Possible gains:
- Lantern Understanding +6
- Leverage +2 if it creates a usable contradiction

### Securing ledger room access
Possible gains:
- Access +6
- Reputation +2 or Leverage +3 depending on method

### Confirming the missing maintenance line
Possible gains:
- Clue Mastery +4
- Leverage +6

### Unlocking the hidden route
Possible gains:
- Access +8
- Lantern Understanding +3

### Finding Tovin and the copy sheet
Possible gains:
- Clue Mastery +8
- Leverage +8
- City Impact +4

### Clean exposure ending
Possible gains:
- Reputation +8
- City Impact +10
- Access +4

### Quiet rescue ending
Possible gains:
- Access +5
- Reputation +4 with local actors
- Leverage +5

### Political bargain ending
Possible gains:
- Leverage +10
- Access +4
- Reputation varies by faction

## Unlock Conditions Should Not Be Purely Numeric

Important design rule:
A tier is necessary for some actions, but not always sufficient.
Some unlocks should require both:
- a track threshold
and
- a narrative condition

Examples:
- Tier 2 Access may still require that Ila trusts the player before the shrine workroom opens
- Tier 2 Leverage may still require the player to actually hold a contradiction or debt
- Tier 3 Clue Mastery may still require enough clues in the board to support a synthesis action

This keeps progression grounded in actual play state.

## UI Display Recommendations

### Default player view
Show:
- track label
- short progress phrase
- recent unlock if relevant

Example:
- Lantern Understanding: Informed
- New capability: You can better distinguish lantern damage from manipulation

### Detailed journal/status view
Show:
- current tier label
- hidden or visible score depending on mode
- most recent gains
- current unlocks
- next tier teaser

### Good next-tier teaser examples
- “At the next tier, you may be able to judge whether unstable testimony is location-linked.”
- “At the next tier, more restricted spaces may open through trust rather than explicit proof.”

## MVP Balance Guardrails

To keep the first case readable and balanced:
- avoid moving more than two tracks significantly in a single ordinary scene
- do not let Reputation explode from one public action unless the ending is dramatic
- do not give high Access without a clear narrative justification
- do not let City Impact outpace the player’s actual visible footprint in the story
- do not gate every interesting action behind raw track thresholds alone

## Design Rules

1. Every tier must unlock a real gameplay change.
2. Learning tracks should feel stable; social tracks can be lost or spent.
3. Access should open space, not just labels.
4. Leverage should create new outcomes, not only dialogue variants.
5. City Impact should mostly arrive through consequences, not accumulation for its own sake.
6. Clue Mastery should improve interpretation, not replace investigation.
7. Numeric thresholds should support the fiction, not overpower it.
8. The first case should move the player meaningfully, but not finish the progression arc.

## Summary

This progression layer makes Lantern City’s core tracks concrete.
It gives the MVP measurable growth, real unlocks, readable pacing, and enough structure to make the player’s gains visible in play.

If implemented well, the player should finish The Missing Clerk able to say:
- I understand lanterns better
- I can go places I could not go before
- people and institutions respond to me differently
- I can turn clues into action more effectively
- the city now reacts to what I do