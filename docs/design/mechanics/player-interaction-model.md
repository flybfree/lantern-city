# Lantern City — Player Interaction Model

## Purpose

This document defines how Lantern City is played from moment to moment.
It translates the existing world, case, NPC, progression, and backend design into a concrete player-facing interaction structure.

The goal is to answer questions like:
- what the player sees on each turn
- what the player can do at any given moment
- how free text and structured actions work together
- how scenes open and close
- how clues, progress, and pressure are surfaced
- how the game helps the player when they are stuck

This is a design document, not an implementation spec.
But it should be specific enough that implementation decisions can follow from it cleanly.

## Core Interaction Principle

Lantern City should use a hybrid interaction model:
- concise narrative text
- a small set of structured available actions
- optional free-text input for conversational or investigative specificity

This means the game is not:
- pure parser fiction
- pure menu selection
- pure chat with an unconstrained LLM

Instead, it should feel like a guided investigative conversation with the city.

## Why a Hybrid Model Fits Lantern City

A hybrid model best supports the project’s goals because it:
- preserves expressive, text-first play
- keeps the player from getting lost in totally open-ended prompts
- makes stateful systems visible and legible
- reduces unproductive interaction loops
- supports narrow request handling on the backend
- gives the player both freedom and structure

This is especially important because Lantern City depends on:
- investigation
- social reading
- clue comparison
- access management
- evolving hidden systems

A purely free-text interface would create too much ambiguity.
A purely menu-based interface would flatten the atmosphere and reduce interpretive play.

## Recommended Presentation Layer

For the MVP, assume a terminal-first or simple text UI.
That UI should always present the current play state in a compact, readable structure.

A typical screen should show:
1. current location and district
2. short narrative scene text
3. notable entities in the scene
4. active case reminder if relevant
5. available actions
6. optional input field for custom phrasing
7. short status strip for recent changes

## The Basic Player Turn

A normal interaction cycle should look like this:

1. The game presents the current scene.
2. The player chooses or types an action.
3. The backend classifies the action.
4. The game resolves state changes.
5. The game returns:
   - concise narrative result
   - what changed
   - new or updated clues
   - updated available actions
   - progress or pressure feedback if relevant
6. The player decides what to do next.

This should feel closer to:
- choose a line of inquiry
- push on a lead
- read local conditions
- use what you know

And less like:
- exhaust every dialogue branch
- guess the right parser phrase
- ask infinitely open-ended questions with no structure

## Player Input Modes

The game should support three input modes.

### 1. Primary mode: structured action selection
This is the default and most important mode.
The player chooses from a short list of context-aware actions.

Examples:
- Speak to Ila Venn
- Inspect the lantern bracket
- Review the missing clerk file
- Travel to the archive steps
- Ask who last saw the clerk
- Press with evidence
- Leave the scene

This mode is important because it:
- keeps the interaction readable
- makes available affordances clear
- reduces dead turns
- aligns naturally with narrow backend requests

### 2. Secondary mode: guided free text
The player may type a custom line inside a known context.
This should be allowed mainly when:
- speaking to an NPC
- asking a question about a clue
- describing a specific investigation angle
- making a social push with custom wording

Examples:
- “Ask whether the outage began before the records changed.”
- “Point out the inconsistency in the dock ledger.”
- “Tell her I know the council inspected the shrine.”

This free text should be interpreted inside the currently active scene and intent category.
It should not replace scene structure.
It should refine an already valid action space.

### 3. Fallback mode: system commands / navigation actions
The player should always be able to issue simple utility actions such as:
- review case
- review clues
- check status
- travel
- wait
- leave
- ask for summary
- ask what matters here

These are not highly expressive, but they are essential for clarity and recovery.

## Design Rule for Input

Free text should add specificity.
Structured actions should provide safety and clarity.
System commands should provide recovery and orientation.

If the player can always do those three things, the game remains both readable and flexible.

## What the Player Should Always Be Able To Do

From almost any active scene, the player should have access to a stable set of evergreen actions.
These may appear directly as buttons/options or as command shortcuts.

### Evergreen actions
- Observe the current area
- Speak to a visible NPC
- Inspect a visible object, record, or clue source
- Review current case
- Review known clues
- Check status / progress
- Ask what stands out here
- Leave / step back

### Conditional evergreen actions
When appropriate, also allow:
- Travel to another location
- Use leverage
- Present evidence
- Ask for names or directions
- Wait and watch
- Revisit a prior lead

Why this matters:
The player should never be trapped in a scene with no obvious next move.
Even if a scene is low-value, the game should preserve orientation and forward motion.

## Default Action Count Per Turn

The UI should usually show:
- 3 to 6 primary available actions
- 0 to 3 secondary actions
- 2 to 4 evergreen utility actions

This keeps decision space readable.

Too few actions creates forced play.
Too many actions creates analysis paralysis and makes the current scene feel shapeless.

## Scene Layout

Every scene should be presented in a consistent format.
The exact visuals can vary later, but the information hierarchy should stay stable.

### Scene header
Should show:
- district name
- location name
- time/pressure note if relevant
- lantern condition if relevant

Example:
- Old Quarter — Shrine Lane
- Lantern condition: dim
- Case pressure: rising

### Scene body
A short narrative block describing:
- what is immediately happening
- what feels unusual or important
- who or what is present
- any visible tension

The scene body should be compact.
Usually 1 to 3 short paragraphs is enough.

### Scene entities
A small readable list of notable things in the scene:
- visible NPCs
- interactable objects
- relevant exits
- active clue hooks

Example:
- Ila Venn, shrine keeper
- lantern bracket with fresh scoring
- archive stairwell
- narrow passage toward the lower court

### Scene actions
A curated list of what the player can do next.
These should be derived from:
- current scene type
- visible entities
- case relevance
- access state
- prior discoveries

### Scene footer / status notes
A minimal strip showing recent state changes such as:
- New clue: maintenance rota fragment
- Reputation improved in the Old Quarter
- Access gained: shrine workroom
- Tension rising between the Memory Keepers and Shrine Circles

## Scene Types and Their Interaction Style

The scene structure doc identifies multiple scene types.
This interaction model now defines how they should feel to play.

### 1. Conversation scenes
Primary interaction:
- choose a question, approach, or pressure tactic
- optionally type a custom phrasing

Player should see:
- NPC identity
- NPC stance or mood
- likely discussion angles
- clean exit options

Good action examples:
- Ask about the clerk
- Ask about the outage
- Mention the altered record
- Press with contradiction
- Change the subject
- End conversation

Conversation scenes should not require the player to discover the existence of basic topics through guesswork.
Important topics should usually be surfaced.
Free text is for nuance, not for discovering the entire space of possible questions from scratch.

### 2. Investigation scenes
Primary interaction:
- choose what to examine
- choose depth or method of inspection
- compare evidence when relevant

Good action examples:
- Examine the lamp housing
- Compare the ledger with the wall registry
- Look for tampering
- Trace recent movement
- Test whether the damage is accidental
- Step back

Investigation scenes should reward attention and comparison.
They should not become hidden-object hunts.

### 3. Transition scenes
Primary interaction:
- choose destination or route
- choose whether to move quickly, cautiously, or observantly

Good action examples:
- Travel to the archive steps
- Take the public route
- Use the lower passage
- Stop to listen to local gossip
- Continue without delay

Transition scenes are useful for:
- rumor delivery
- pressure updates
- travel consequences
- changing local atmosphere

### 4. Confrontation scenes
Primary interaction:
- choose how to apply pressure
- choose whether to reveal information, withdraw, bargain, or escalate

Good action examples:
- Present the evidence
- Ask for cooperation
- Threaten exposure
- Offer discretion
- Call in a favor
- Withdraw for now

Confrontation scenes should make leverage and reputation matter visibly.

### 5. Revelation scenes
Primary interaction:
- interpret a discovery
- choose what to believe, reveal, conceal, or act on

Good action examples:
- Conclude the outage was staged
- Keep the finding private
- Share it with Ila Venn
- Bring it to the archive office
- Follow the hidden implication

These scenes should often shift the meaning of previous clues.

### 6. Fallout scenes
Primary interaction:
- respond to consequences
- choose where to go next
- decide who to support, confront, or avoid

Good action examples:
- Read the district reaction
- Visit the affected location
- Meet the faction representative
- Quiet the rumor
- Let the matter stand

Fallout scenes make persistence visible.

## Conversation Model

Lantern City should not use exhaustive dialogue trees.
It should use topic clusters with optional custom phrasing.

### Recommended conversation structure
Each meaningful conversation should offer:
- 2 to 4 obvious topical questions
- 1 to 2 pressure or inference actions if earned
- 1 redirect or exit action
- optional custom ask field

### Example topic cluster
For a shrine keeper tied to a lantern outage:
- Ask about the outage
- Ask about the missing clerk
- Ask who inspected the shrine recently
- Ask why the records no longer match
- Present evidence from the archive ledger
- End the conversation

### Important rule
A player should not need to manually invent the exact right question wording to make progress.
If a topic is reasonably available from scene context, the game should surface it.

## Investigation Model

Investigation should be built around meaningful examination choices rather than broad “search everything” prompts.

### Investigation actions should usually be framed as
- examine a thing
- compare two things
- test a theory
- interpret uncertain evidence
- use a learned capability

### Investigation should produce one or more of
- a new clue
- a clue refinement
- a clue reliability change
- a new contradiction
- a new route or lead
- a lantern insight
- a reason to revisit an NPC

### Anti-pattern to avoid
Do not force players to repeatedly type generic commands like:
- inspect room
- inspect wall
- inspect floor
- inspect lamp
- inspect note

Instead, the game should present meaningful nodes of attention.

## Travel and Movement Model

Travel should be explicit, but lightweight.

The player should think in terms of moving between meaningful places, not micromanaging street-by-street pathfinding.

### Movement layers
1. District travel
2. Location travel within a district
3. Hidden or restricted route access

### District travel should show
- known destinations
- access restrictions
- risk or pressure notes
- whether travel advances time or pressure

### Location travel should show
- nearby important places
- current known relevance
- whether someone is likely present
- whether the route is blocked, risky, or hidden

### Hidden routes
These should become visible through:
- clues
- trust
- access
- lantern understanding
- local reputation

### Travel design rule
Travel should be a meaningful transition, not dead friction.
If nothing interesting can happen during a route, it should resolve quickly.
If the route matters, it should become a short transition scene.

## Case Board and Journal Model

The player needs a strong external memory structure.
Lantern City should not rely on the player remembering everything from prose alone.

The game should therefore expose two distinct review surfaces.

### 1. Case Board
The case board is the active investigation view.
It should show:
- case title
- current case status
- current objective or strongest open lead
- key people
- key places
- key unresolved questions
- known pressure or urgency
- next plausible avenues

This should answer:
- what am I trying to solve right now?
- what are the live threads?
- what still does not make sense?

### 2. Journal / Chronicle
The journal is the broader memory view.
It should show:
- major events
- discovered clues
- district observations
- notable relationship changes
- unlocked locations
- important lantern findings
- resolved and unresolved fallout

This should answer:
- what has happened in this run?
- what have I learned about the city?
- what changed because of me?

## Clue Presentation Model

Clues should not just exist in hidden backend state.
They should be visible, categorized, and revisitable.

Each clue entry should expose:
- clue title or short summary
- source
- current reliability
- linked people/places/cases
- what it suggests
- what remains uncertain

### Reliability labels
Good labels include:
- solid
- credible
- uncertain
- distorted
- contradicted
- unstable

This fits Lantern City especially well because lantern and Missingness systems can alter certainty.

### Clue UX rule
When a clue changes meaning, the game should tell the player.
For example:
- Clue updated: witness account now marked contradicted
- Clue clarified: outage predates the clerk’s disappearance

## Progress Feedback Model

Progress should be visible, but not noisy.

### Default mode
After meaningful actions, show short natural-language feedback such as:
- Lantern Understanding increased
- You gained access to the shrine workroom
- Ila Venn now trusts you more
- The case has narrowed
- District tension is rising

### Optional detailed mode
Players who want more detail should be able to inspect:
- track name
- tier or label
- recent gains/losses
- cause of change
- unlocked capability or implication

### Best practice
Do not print full numeric deltas every turn by default.
Reserve detailed breakdowns for status and review screens.

## Relevance Signaling Model

The game should help the player understand what matters without making the experience feel mechanical.

### Good soft signals
- a named NPC receives a stronger introduction
- an NPC reacts with tension or guarded specificity
- an object is described with unusual precision
- a clue entry appears in the case board
- an action is marked as new, risky, or significant
- a post-scene summary highlights what was gained

### Good explicit signals
Use sparingly, but clearly when needed:
- New lead
- Access gained
- Clue updated
- Case advanced
- Pressure increased

### Important rule
The player should not need to guess whether a scene produced something meaningful.
The result should be legible after the fact.

## Being Stuck: Recovery Model

Lantern City must assume that players will sometimes lose the thread.
The UX should recover them gracefully without destroying the feeling of discovery.

### Recovery actions the game should always support
- What matters here?
- Review current case
- Review unresolved questions
- Show strongest leads
- Who should I talk to next?
- Where can I go from here?
- What changed recently?

### Recovery response style
The game should answer in diegetic but clear language.
It should not say:
- “Try option 3.”

It should say things like:
- “The strongest unresolved thread remains the altered archive record.”
- “Ila Venn and the archive clerk are the two people most directly tied to the outage.”
- “You still do not know whether the lantern damage caused the record change or covered for it.”

### Stuck-state design rule
Recovery tools should point toward live uncertainty, not solve the mystery automatically.

## Failure and Refusal UX

Not every action should succeed.
But failures should remain informative.

### Good failure outcomes
- an NPC refuses, but reveals why
- a route is blocked, but hints at another access path
- a clue remains uncertain, but gives a better question
- a confrontation closes one door and opens another
- waiting makes pressure worse, but clarifies stakes

### Bad failure outcomes
- “Nothing happens.”
- “You can’t do that.” with no redirect
- hard dead ends with no new information

### Rule
A refused action should usually create one of:
- explanation
- redirect
- consequence
- escalation

## Time and Pressure in the UI

Even before the full time-pressure model is formally designed, the interaction model should reserve space for pressure visibility.

The player should occasionally see notes such as:
- Case pressure: low / rising / urgent
- District tension: stable / uneasy / unstable
- Lantern condition: dim / flickering / altered

This keeps the world feeling active and helps the player understand that delay has meaning.

## Action Resolution Tone

Each action result should generally answer five questions:
1. What happened?
2. What changed?
3. What did I learn?
4. What can I do now?
5. Did pressure rise or ease?

Not every answer must be explicit every turn, but the response composer should treat these as the default resolution checklist.

## Example Turn Format

Below is a representative interaction shape for the MVP.

```text
Old Quarter — Shrine Lane
Lantern condition: dim
Case pressure: rising

Rain threads down the shrine glass in narrow silver lines. Ila Venn waits beneath the awning, one hand on the latch to the workroom. The street lantern beside her is still burning, but badly: the light wavers as though it cannot decide what belongs in this street and what does not.

Notable here:
- Ila Venn, shrine keeper
- damaged lantern bracket
- shrine workroom door
- path toward the archive steps

Case: The Missing Clerk
Open question: Did the lantern outage begin before the clerk vanished?

Available actions:
1. Speak to Ila Venn
2. Inspect the damaged lantern bracket
3. Ask to enter the workroom
4. Travel to the archive steps
5. Review current clues
6. Leave the lane

Optional input:
> ask ila whether the council inspected the lantern before the outage

Recent changes:
- Clue updated: archive ledger now marked uncertain
- Reputation improved in the Old Quarter
```

This format gives:
- atmosphere
- legibility
- available affordances
- case context
- custom expression space

## MVP Recommendation

For the MVP, the player interaction model should specifically be:
- text-first
- hybrid structured + guided free text
- location-based
- scene-based
- case-board supported
- clue-journal supported
- terminal-friendly

The MVP should not attempt:
- unrestricted parser simulation
- full sandbox command freedom
- complex inventory verb systems
- large dialogue trees
- dense HUD-heavy presentation

## Interaction Design Constraints for the MVP

To keep the MVP focused, use these constraints:
- show only the current active slice
- keep scene text concise
- present a short action list every turn
- allow free text only inside valid scene context
- provide evergreen recovery commands
- always surface what changed after a meaningful action
- make it possible to leave almost any scene cleanly

## Relationship to Backend Design

This interaction model aligns with the existing backend philosophy.
It supports:
- narrow request classification
- small context packets
- bounded generation per turn
- cached scene summaries
- structured response composition
- explicit state updates after each action

This is important because the interaction design should not fight the architecture.
It should reinforce the engine-owned, minimal-context, lazy-generation approach.

## Design Rules

1. The player should always know what they can do next.
2. Free text should refine play, not replace structure.
3. Important discoveries should be surfaced clearly.
4. Scenes should close cleanly when value is exhausted.
5. Failure should redirect, inform, or escalate.
6. The case board should preserve investigative coherence.
7. The journal should preserve city memory.
8. The UI should make progress and pressure legible without becoming noisy.
9. Travel should connect meaningful places, not create dead friction.
10. The player should never have to solve the interface before solving the mystery.

## Summary

Lantern City should play as a guided investigative text experience with selective expressive freedom.
The player should feel like they are reading the city, pursuing leads, and applying insight inside a living system.

The interaction model should therefore combine:
- atmospheric narrative presentation
- visible structured affordances
- optional custom phrasing inside bounded contexts
- strong clue and case review tools
- reliable recovery when the player loses the thread

If this model is followed, Lantern City should remain:
- text-first
- legible
- expressive
- stateful
- architecturally grounded
- playable without confusion