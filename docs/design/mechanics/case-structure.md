# Lantern City — Case Structure

## What a Case Is

A case is a quest, investigation, conflict, or mystery arc that takes place inside a persistent city instance.

The city remains alive across cases.
Cases are the story units that move the city forward.

## What Starts a Case

A case begins when the player receives a meaningful problem, such as:
- a missing person
- a lantern outage
- a district dispute
- a faction request
- a strange rumor
- a civic inconsistency
- a Missingness-related anomaly

A case can start through:
- direct assignment
- rumor discovery
- overheard conversation
- faction pressure
- accidental discovery
- a consequence of a previous case

## Case Components

Each case should have:
- a title or shorthand label
- a core mystery or objective
- involved NPCs
- affected districts
- relevant factions
- clues discovered so far
- open questions
- visible state changes
- hidden state changes
- success, partial success, and failure outcomes

## Case Size

Cases can vary in size.

### Small case
- 1 district
- a few NPCs
- a short chain of clues
- fast resolution

### Medium case
- 1 to 2 districts
- multiple NPCs and competing leads
- moderate state changes
- may require several scenes

### Large case
- multiple districts
- faction involvement
- lantern system changes
- persistent consequences
- may reshape the city

## Case Flow

A typical case follows this pattern:

1. Trigger
   The player learns something is wrong.

2. Framing
   The problem becomes legible as a case.

3. Investigation
   The player gathers clues, talks to NPCs, and tests theories.

4. Pressure
   The city or factions respond to the player’s actions.

5. Breakthrough
   The player finds the key truth or structural cause.

6. Resolution
   The player solves, alters, or partially resolves the case.

7. Fallout
   The city updates, and the results affect future play.

## Case States

A case should be able to sit in one of several states.

### Active
The player is still investigating.

### Stalled
The player lacks enough information, access, or leverage to proceed.

### Escalated
The situation has worsened or expanded.

### Solved
The main truth has been found and the player has meaningfully addressed it.

### Partially Solved
The player has improved the situation, but not fully resolved it.

### Failed
The player lost the opportunity, but the city moved on with consequences.

## Case Resolution

The player triggers resolution with `case <case_id>`. The engine evaluates the
case's resolution paths in priority order (priority 1 = best outcome) and picks
the first path where the player has enough **credible** clues.

### Resolution paths

Each case is generated with 2–5 resolution paths, each specifying:
- `outcome_status` — `solved`, `partially solved`, or `failed`
- `required_credible_count` — minimum number of credible clues needed
- `required_clue_ids` — specific clues that must be credible
- `summary_text` — narrative description of the outcome
- `fallout_text` — city consequences

The engine walks paths from priority 1 downward. The last path is the fallback
(always reached if no earlier path is satisfied).

### Outcome tiers

| Outcome | Condition | Gains |
|---|---|---|
| `solved` | Enough credible clues for the best path | +reputation, +city_impact, +clue_mastery |
| `partially solved` | Some evidence but not enough for `solved` | +lantern_understanding, +clue_mastery |
| `failed` | No path satisfied; fallback applied | +lantern_understanding (small) |

### What determines credibility

Clue reliability is shaped by the lantern condition of the district where the
clue was found, and by NPC dialogue. A clue starts as `credible`, `uncertain`,
or `unstable`. Talking to relevant NPCs can raise reliability; contradicting
testimony can lower it.

**Reliability is what gates outcomes — not clue count.**

### Improving outcomes before resolving

Before typing `case <case_id>`:
1. Check `clues` — identify which are `uncertain` or `unstable`
2. `inspect` locations in the involved districts to find more clues
3. `talk` to NPCs connected to the case — dialogue can raise clue reliability
4. Re-enter districts with better lantern conditions if possible

### Closure is permanent

Cases close on resolution and cannot be re-opened. A `partially solved` case
does not become `solved` later. When the active case pool drops below two open
cases, the engine generates a new latent case to replace closed ones.

## Case Closure

A case closes when one of these is true:
- the player resolves it with `case <case_id>`
- the core mystery has been addressed (any outcome)

Closure does not always mean happy ending.
It means the case has reached a new stable state and the city moves on.

## How Many Cases Can Be Active

Recommended default:
- 1 primary case
- 0 to 2 secondary cases
- optional minor rumors or background threads

This prevents the player from being overwhelmed while still allowing a living city with multiple pressures.

## Relationship Between Cases and the City

Cases should change the persistent city instance.
Possible effects:
- district stability shifts
- lantern conditions change
- factions gain or lose influence
- NPC memories update
- access opens or closes
- new cases emerge from the fallout

## Design Rule

A case is not just a mission objective.
It is a way the city reveals itself, changes state, and remembers the player.

Every case should leave the city different from how it was before.
