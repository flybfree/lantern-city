# Lantern City — Lantern and Missingness Rules

## Purpose

This document gives Lantern City’s lantern system and Missingness system hard mechanical edges for the MVP.
It defines:
- what each lantern state does
- how lantern state affects clues, witnesses, access, and movement
- how Missingness pressure behaves
- what is deterministic versus probabilistic
- how alteration differs from damage
- what stabilization, restoration, and permanent loss mean
- how these systems should interact with the request lifecycle and rule engine

This is not meant to make the setting overly rigid.
It is meant to make the core systems predictable enough that the engine can own state cleanly while still leaving room for mystery.

## Design Goal

Lantern City should feel strange, but not arbitrary.
The player should be able to learn patterns.
The engine should be able to apply consequences consistently.
The LLM should generate local expression, not invent core causal rules on the fly.

## Core Rule

Lantern state determines local coherence.
Missingness pressure determines how hard the world is pushing toward absence, contradiction, and instability.

Together, they shape:
- clue reliability
- witness consistency
- route certainty
- access gating
- NPC confidence and caution
- district stability
- case pressure

## Two-Layer System

For the MVP, treat these as two linked but distinct layers.

### Layer 1: Lantern condition
This is the local or district state of the light system.
It is the main modulator of reliability and access.

### Layer 2: Missingness pressure
This is the anomaly pressure acting on a district, location, case, or identity thread.
It is the main modulator of whether contradiction deepens into loss.

### Rule of interaction
Lantern condition shapes how protected an area is.
Missingness pressure shapes how much stress that area is under.

In simple terms:
- good lantern condition can buffer pressure
- bad lantern condition amplifies pressure
- altered lantern condition can redirect pressure selectively instead of merely reducing or increasing it

## Scope Levels

Both lantern and Missingness rules may operate at different scopes.

### 1. District scope
Applies to:
- general witness quality
- public mood
- movement feel
- rumor density
- district stability

### 2. Location scope
Applies to:
- scene-level clue reliability
- scene-specific witness confidence
- route and access anomalies
- local investigation difficulty

### 3. Object or identity scope
Applies to:
- a specific clue
- a person’s record status
- a specific route or lantern node
- a hidden chamber or archive file

### Rule
For any request, the engine should use the narrowest relevant scope first.
If a location has a stronger local condition than the district default, the location wins.

## Lantern State Set

For the MVP, use five lantern states:
- bright
- dim
- flickering
- extinguished
- altered

These should be explicit engine states, not just descriptive text.

## Missingness Pressure Levels

For the MVP, use four pressure levels:
- none
- low
- medium
- high

If needed internally, these can map to a 0.0 to 1.0 score.

Suggested ranges:
- none: 0.00 to 0.09
- low: 0.10 to 0.34
- medium: 0.35 to 0.64
- high: 0.65 to 1.00

The UI can use labels while the engine stores numeric values.

## Deterministic vs Probabilistic Effects

To keep the system learnable, use this split.

### Deterministic effects
These should always happen when the condition is present.
Examples:
- bright improves baseline witness confidence
- extinguished blocks confidence-dependent access checks
- altered changes which evidence or identities are selectively distorted
- high Missingness pressure increases the chance that unresolved contradictions worsen

### Probabilistic effects
These should only apply when the engine needs variability inside a constrained range.
Examples:
- whether a witness account becomes merely uncertain or fully contradicted
- whether a location transition generates a route anomaly scene
- whether an unstable clue degrades this turn or the next

### MVP rule
Default to deterministic state shifts whenever possible.
Use probabilistic variation only for:
- uncertainty grading
- scene variation
- escalation timing inside already dangerous conditions

This keeps the game feeling systemic rather than random.

## Lantern Condition Rule Table

## 1. Bright

### Fictional meaning
The lantern network is functioning normally and publicly.
Memory anchoring is strong.
The district feels administratively and socially coherent.

### Deterministic effects
- witness confidence gets a positive modifier
- route certainty is high
- access checks based on ordinary legitimacy are easier
- clue reliability is less likely to degrade from local condition alone
- civic and official language carries more weight socially

### Mechanical summary
- witness confidence: +2 step bonus
- clue degradation risk from lantern condition: minimal
- route anomaly risk: minimal
- public-access friction: reduced
- rumor distortion: reduced

### Best use in play
Bright is not “truth mode.”
It is “stable official reality mode.”
This means a bright district can still support lies, but those lies will be cleaner and harder to challenge with vague suspicion.

## 2. Dim

### Fictional meaning
The system is under strain, neglected, or partially weakened.
The district still functions, but certainty is thinner than it should be.

### Deterministic effects
- witness hesitation rises
- clue reliability becomes more context-dependent
- rumors spread faster than official correction
- movement remains possible but less socially or emotionally comfortable
- NPC caution rises in scenes tied to sensitive facts

### Mechanical summary
- witness confidence: -1 step
- clue reliability: one step more fragile if based only on testimony
- route anomaly risk: low
- public-access friction: slight increase
- social ambiguity: increased

### Best use in play
Dim is the MVP’s main “something is wrong here” state.
It should increase uncertainty without making scenes unusable.

## 3. Flickering

### Fictional meaning
The system is actively unstable.
Local coherence shifts moment to moment.
People disagree more sharply and routes feel less trustworthy.

### Deterministic effects
- witness consistency is unstable
- scene-based contradictions become common
- route certainty drops
- lantern-linked clues gain volatility tags more often
- Missingness escalation checks become more severe

### Mechanical summary
- witness confidence: -2 steps
- testimony-only clues often degrade one level unless corroborated
- route anomaly risk: medium
- public-access friction: moderate
- Missingness amplification: +1 pressure effect tier for local checks

### Best use in play
Flickering is the state where the player should start trusting comparison, physical evidence, and cross-location reasoning more than any single account.

## 4. Extinguished

### Fictional meaning
The local light system has failed or been removed.
The area is vulnerable both socially and metaphysically.

### Deterministic effects
- witness confidence collapses
- route coherence is poor
- records and identities tied to the area become much more vulnerable
- movement or access may be blocked, hidden, or rerouted
- unofficial activity increases because official presence weakens
- Missingness escalation checks become severe

### Mechanical summary
- witness confidence: minimum baseline unless protected by other factors
- testimony-only clues cannot be upgraded without outside corroboration
- route anomaly risk: high
- public-access friction: high or route-blocking
- Missingness amplification: +2 pressure effect tiers for local checks

### Best use in play
Extinguished should be rare in the MVP and strongly consequential.
It should create danger and opportunity, not just flavor.

## 5. Altered

### Fictional meaning
The lantern is not simply damaged.
It has been intentionally redirected, edited, bound differently, or tuned toward a selective effect.

### Core design rule
Altered is not merely “worse than extinguished.”
It is selective.
It changes what is coherent for some things and incoherent for others.

### Deterministic effects
- at least one category is selectively distorted
- another category may remain stable or become artificially stable
- testimony, identity, route logic, or document continuity may be affected unevenly
- ordinary inspection may misread the site as normal damage unless Lantern Understanding is high enough or corroboration exists

### Required altered profile fields
Any altered lantern state in the engine should specify at least:
- altered_target_domain
- altered_effect_mode
- altered_scope
- altered_owner_or_suspected_controller if known

### Allowed target domains for MVP
- testimony
- records
- identity
- route
- access

### Allowed effect modes for MVP
- suppress
- redirect
- split
- stabilize selectively
- distort selectively

### Example altered state
- target domain: records
- effect mode: suppress
- scope: within two blocks of archive steps

Effect:
- records tied to a target thread degrade or contradict more easily
- unrelated street navigation remains mostly normal

### Mechanical summary
- witness confidence: variable by target domain
- clue reliability: selectively unstable
- route anomaly risk: variable
- access friction: variable
- Missingness amplification: targeted rather than global

### Best use in play
Altered is the signature Lantern City state.
It should drive the most interesting cases because it creates structured unreality rather than random unreality.

## Witness Confidence Rules

Witness confidence is not the same as honesty.
It measures how stable, coherent, and actionable a witness account is under current conditions.

For the MVP, use five witness confidence states:
- strong
- credible
- uncertain
- unstable
- unusable

### Base witness confidence by lantern condition
- bright -> credible to strong
- dim -> credible to uncertain
- flickering -> uncertain to unstable
- extinguished -> unstable to unusable
- altered -> depends on target domain and witness relation to it

### Confidence adjustment factors
Adjust witness confidence by one step up or down based on:
- whether the witness was inside or outside the affected zone
- whether the witness has direct experience or secondhand knowledge
- whether the witness has a motive to conceal
- whether the player has corroborating physical evidence
- whether Lantern Understanding is high enough to ask clarifying questions

### Rule
The engine should never silently convert “lying” into “unstable.”
Dishonesty and instability are different flags.
A witness can be:
- honest but uncertain
- dishonest but confident
- frightened and inconsistent
- correct for the wrong reasons

## Clue Reliability Rules

Clues should use six reliability states in the MVP:
- solid
- credible
- uncertain
- distorted
- contradicted
- unstable

### Meaning of each reliability state
- solid: highly actionable and locally well supported
- credible: likely true, but not fully locked down
- uncertain: incomplete or under-supported
- distorted: probably affected by lantern state or Missingness
- contradicted: conflicts with another credible source
- unstable: may degrade or change meaning as state shifts

### Reliability by source type
#### Physical clue
Examples:
- soot pattern
- tool mark
- copied paper
- damage on lantern bracket

Baseline:
- generally more resistant to lantern-state degradation than testimony

#### Document clue
Examples:
- roster entry
- maintenance ledger
- permit record

Baseline:
- highly sensitive to altered-record effects and Missingness pressure

#### Testimony clue
Examples:
- what an NPC says they saw
- timeline recollection
- secondhand rumor

Baseline:
- most sensitive to lantern condition and local pressure

#### Composite clue
Examples:
- a clue produced by comparing testimony, record, and physical sign

Baseline:
- usually improves in reliability if sources converge

## Reliability shift rules by lantern state

### Bright
- physical clues: no automatic downgrade
- document clues: no automatic downgrade unless altered targets records
- testimony clues: can upgrade more easily if corroborated

### Dim
- physical clues: stable unless already fragile
- document clues: may shift from credible to uncertain if tied to contested continuity
- testimony clues: often drop one step unless corroborated

### Flickering
- physical clues: usually stable, but context interpretation may become uncertain
- document clues: may become uncertain or contradicted
- testimony clues: often drop one to two steps unless outside-zone corroboration exists

### Extinguished
- physical clues: survive best, but meaning may be hard to place without comparison
- document clues: often unstable or distorted if locally tied
- testimony clues: usually unstable or unusable without external support

### Altered
- only clues within the altered target domain should degrade automatically
- clues outside the target domain should not be penalized just because the lantern is altered

This is critical.
Altered must stay selective.

## Route and Movement Rules

For the MVP, route certainty should use four states:
- clear
- uneasy
- unreliable
- compromised

### Route certainty by lantern condition
- bright -> clear
- dim -> uneasy
- flickering -> unreliable
- extinguished -> compromised
- altered -> depends on whether route is the target domain

### Effects on play
#### Clear
- normal movement
- no extra route scene required unless narratively useful

#### Uneasy
- normal movement with occasional atmospheric warning or rumor scene

#### Unreliable
- movement may trigger a short transition scene
- the player may arrive with shifted assumptions, new rumor, or slight delay

#### Compromised
- movement may require alternate route, special access, or scene resolution
- hidden or unofficial actors become more likely to matter

### MVP rule
Do not use route uncertainty to annoy the player.
Use it to:
- reveal state
- create redirect scenes
- reinforce a district’s identity
- justify hidden-route discoveries

## Access and Permission Rules

Lantern state can affect not just movement, but whether spaces are considered properly accessible.

### Bright
- public legitimacy is strong
- formal access methods work best

### Dim
- informal access gains value
- weakly justified denials become more common

### Flickering
- institutions hesitate
- local workers improvise
- access rules become inconsistent

### Extinguished
- some official routes or rooms may be shut entirely
- unofficial entry becomes more important

### Altered
- access may be selectively denied or opened to the wrong people
- the player may discover that “authorized” and “actually reachable” are no longer aligned

## Missingness Pressure Rule Table

Missingness pressure should measure how likely the world is to produce absence, contradiction, erasure, or displaced continuity around a target domain.

## None
### Meaning
No active anomaly pressure beyond ordinary urban ambiguity.

### Effects
- contradictions are likely social or political, not metaphysical
- no passive Missingness escalation

## Low
### Meaning
Subtle anomaly pressure exists, but it is mostly background.

### Effects
- some clues may feel incomplete
- fragile records or identities are slightly easier to contest
- escalation requires poor lantern conditions or targeted alteration to matter much

## Medium
### Meaning
The anomaly is actively present in the district, case, or identity thread.

### Effects
- unresolved contradictions worsen over time
- unstable lantern conditions become much more dangerous
- some identities, records, or route threads begin to drift if left unattended

## High
### Meaning
The anomaly is forceful and ongoing.
Without stabilization, absences and contradictions will deepen.

### Effects
- unresolved clue states degrade faster
- witness reliability collapses in affected zones
- record contradictions can harden into civic absence
- hidden or displaced persons become harder to recover cleanly

## Missingness Target Domains

Like altered lanterns, Missingness pressure should often apply to a target domain.
For the MVP, support these target domains:
- person
- record
- route
- event
- place
- family line

### Example
In The Missing Clerk:
- primary target domain: person plus record
- secondary target domain: event timeline

This is why Tovin is both physically hidden and bureaucratically unstable.

## Missingness Propagation Rules

Propagation means pressure spreading from one unstable node into related nodes.
The MVP does not need a huge simulation, but it should support limited spread.

### Propagation preconditions
Missingness should spread when at least two of these are true:
- lantern condition is flickering, extinguished, or altered in the relevant scope
- pressure is medium or high
- contradiction remains unresolved across multiple scenes
- no stabilizing action has been taken
- the target domain is repeatedly stressed by official denial, poor records, or bad routing

### Allowed MVP propagation paths
- person -> record
- record -> family line
- route -> event timeline
- place -> witness consistency

### Example MVP propagation
If Tovin remains unresolved under medium or high pressure:
- his roster entry may degrade further
- witnesses may become less certain of his recent movements
- the timeline of the outage may split more sharply

## Stabilization, Restoration, and Permanent Loss

These three states must be clearly separated.

## Stabilization
### Meaning
The system stops worsening.
Future degradation is slowed or halted.

### Does it restore what was lost?
No, not by itself.
It prevents further collapse.

### Example
Repairing or correctly tending the affected lantern may stabilize witness inconsistency without fully restoring every damaged record.

## Restoration
### Meaning
A damaged or unstable thread is brought back into coherence with enough evidence or corrective action to function again.

### Does it require proof?
Usually yes.
Restoration should require some combination of:
- stabilization
- corroborating evidence
- access to corrective authority or ritual capacity
- enough Clue Mastery or Lantern Understanding to interpret correctly

### Example
Tovin’s existence can be restored administratively only if the player recovers enough proof and gets it accepted or impossible to deny.

## Permanent Loss
### Meaning
A thread has degraded beyond clean recovery in the current case.
The city may still react to the loss, but the original continuity cannot be fully restored now.

### MVP use
Use this sparingly.
Permanent loss should be a major consequence, not normal case texture.

### Example
If the player delays too long and the case is buried, Tovin may survive physically but remain civically erased for the rest of the run, or a key record chain may be unrecoverable except through later arc-level work.

## Rule for Recovery Quality

Recovery should be graded.
A case does not need to be binary.
For the MVP, allow outcomes such as:
- stabilized but unresolved
- restored privately but not publicly
- publicly corrected but politically distorted
- permanently damaged but narratively exposed

This fits Lantern City much better than simple success/failure.

## Rule Engine Application Order

When a request touches lantern or Missingness logic, the engine should evaluate in this order:

1. Determine active scope
   - district, location, object, or identity
2. Read lantern condition
3. Read Missingness pressure and target domain
4. Apply deterministic lantern effects
5. Apply deterministic Missingness effects
6. Evaluate whether altered-target rules override general rules
7. Adjust witness confidence, clue reliability, route certainty, and access state
8. Only then, if needed, apply bounded probabilistic variation
9. Persist updated states and expose player-facing changes

This order matters.
Lantern state defines protection or distortion conditions before Missingness pressure tries to deepen them.

## Player-Facing Feedback Rules

The game should surface these systems clearly enough to be learnable.

### Good player-facing outputs
- “The witness seems less certain near this light.”
- “This record appears locally unstable.”
- “The route is still passable, but not trustworthy.”
- “The lantern has been altered, not merely damaged.”
- “You stabilized the site, but did not fully restore what was lost.”

### Avoid
- raw hidden-state dumps in normal play
- unexplained clue downgrades
- contradictions that appear with no traceable systemic cause

## MVP Mapping for The Missing Clerk

Use this case as the reference implementation.

### Old Quarter district default
- lantern condition: dim
- local archive-adjacent node: altered
- Missingness pressure: medium
- target domains: person, record, event timeline

### Archive Steps / Shrine Lane area
Suggested operational behavior:
- testimony about timing is uncertain or contradicted
- physical lantern evidence remains credible
- records tied to Tovin are vulnerable to suppression or contradiction

### Service Passage and hidden chamber
Suggested operational behavior:
- physical clues become stronger than public narrative
- route access depends more on clue convergence than public permission
- finding Tovin can halt propagation on the person domain even before full record restoration

## Guardrails Against Chaos

To keep the system from feeling arbitrary:
- do not degrade every clue just because pressure is high
- do not let altered act like random corruption
- always define target domains for selective effects
- make physical evidence more stable than testimony under bad conditions
- let players meaningfully improve states through action
- make “stabilized” a real and useful outcome even when “restored” is not yet possible

## Design Rules

1. Lantern state must always change something systemic, not just description.
2. Missingness must pressure continuity, not simply create spooky flavor.
3. Altered is selective, not generic chaos.
4. Physical evidence should usually outlast testimony under instability.
5. Stabilization and restoration must remain distinct.
6. The player must be able to learn these rules through play.
7. Mystery should come from hidden causes and selective scope, not random inconsistency.
8. The engine must remain the source of truth for all state changes.

## Summary

These rules make lanterns and Missingness operational for the MVP.
Lantern state defines how coherent a place is.
Missingness pressure defines how hard reality is being pushed toward contradiction or absence.

Together, they create a system where the player can:
- compare witnesses intelligently
- trust physical evidence appropriately
- understand why some routes or records fail
- intervene to stabilize a district
- decide whether a truth can be restored, merely contained, or lost