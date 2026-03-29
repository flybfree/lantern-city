# Lantern City — NPC Interaction System

## Purpose

This system makes NPC conversations readable, useful, and paced well.
The player should be able to tell when an NPC is:
- worth deeper attention
- likely to provide a clue
- useful only for atmosphere
- a lead to someone more important

The goal is to avoid long, unproductive conversations while still preserving discovery and mystery.

## Design Principles

1. Important NPCs should feel discoverable
2. Unimportant NPCs should still feel alive
3. Most conversations should produce value quickly
4. The player should always have a clean way to exit
5. NPC relevance should be signaled without fully removing mystery

## NPC Categories

### 1. Lead NPCs
NPCs who can directly advance the story.
They may:
- reveal key clues
- unlock locations
- alter faction state
- expose hidden motives
- move a case forward

### 2. Informants
NPCs who may not advance the main plot directly, but provide useful knowledge.
They may:
- point the player to another character
- clarify district history
- explain a strange local pattern
- offer useful context

### 3. World NPCs
NPCs who add texture and local life.
They may:
- reinforce atmosphere
- provide rumors
- reflect district mood
- reveal how ordinary people interpret events

### 4. Ambient NPCs
NPCs who mostly exist to make the city feel inhabited.
They should be easy to exit from quickly and should rarely require long conversation unless promoted later.

## Relevance Signals

The player should be able to tell, within the first exchange or two, whether an NPC is worth deeper attention.

Good signals include:
- the NPC knows a specific name, place, or event before the player mentions it
- the NPC reacts strongly to lantern conditions, Missingness, or faction tension
- the NPC is directly tied to the current case
- the NPC speaks with tension, hesitation, or contradiction
- the NPC offers a concrete lead
- the NPC interrupts normal flow to seek the player out
- the NPC is associated with restricted spaces, records, rituals, or debts

## Conversation Phases

Each meaningful conversation should generally move through three phases.

### 1. Opening
The NPC establishes identity, mood, and immediate context.

Questions the player is implicitly asking:
- Who are you?
- Why are you talking to me?
- Do you matter to this case?

### 2. Value Check
The conversation quickly tests whether the NPC can offer useful information.

Questions the player is implicitly asking:
- Do you know anything relevant?
- Are you hiding something?
- Should I keep talking?

### 3. Exit or Deepen
The player either moves on or decides to dig deeper.

Questions the player is implicitly asking:
- Is this a lead?
- Is this a rumor source?
- Is this a gatekeeper?
- Is this just flavor?

## Conversation Length Rule

If an NPC is not story-relevant, the game should usually let the player exit cleanly after a short exchange.

Recommended rule:
- 1 to 3 meaningful back-and-forth turns for ambient or world NPCs
- 3 to 6 turns for informants
- longer only when the NPC is clearly a lead or the player keeps uncovering new value

The game should avoid forcing the player to exhaust dialogue trees.

## Hidden NPC Utility

An NPC does not need to be a major story node to be useful.
Even minor NPCs should ideally do at least one of the following:
- reveal a rumor
- redirect the player to a more relevant person
- provide local color that changes how the player reads the district
- hint at hidden state
- confirm or deny an assumption

## Story Relevance Indicators

The game should support a soft visual or textual cue system for NPC relevance.

Possible approaches:
- subtle dialogue tags
- phrase cues in the NPC introduction
- a “relevance” tone in the conversation prompt
- iconography for lead vs rumor vs flavor NPCs
- a post-conversation summary showing what was gained

The system should help the player notice usefulness without making everything feel gamified or obvious.

## Example NPC Flow

### Flavor NPC
- greets the player
- comments on the weather or district mood
- has one rumor line
- offers a clean exit

### Informant NPC
- knows about a missing person, lantern outage, or faction dispute
- provides a named lead
- suggests where to go next
- may have one follow-up question

### Lead NPC
- reveals contradiction or concealed knowledge
- reacts to the player’s reputation or leverage
- can shift the state of the case
- may require persuasion, access, or evidence

## Exit Tools

The player should always have ways to leave a conversation without penalty.
Useful exits include:
- “That’s enough for now.”
- “I’ll come back if I need more.”
- “Who else should I ask?”
- “What should I look for?”
- “I have what I need.”

This keeps dead-end NPCs from becoming a burden.

## Behind-the-Scenes Requirements

For each tracked NPC, the game should know:
- category
- current relevance to the active case
- what they know
- what they want
- what they are hiding
- how they feel about the player
- whether they can redirect the player to someone else

This lets the system adapt without making every NPC a full quest giver.

## Recommended Progression Logic

Early game:
- the player learns to identify useful NPCs quickly
- many NPCs are simple, but a few are clearly loaded with meaning

Mid game:
- the player begins recognizing patterns in relevance cues
- informants and leads become easier to separate from flavor NPCs

Late game:
- the player can infer hidden relevance before it is explicitly stated
- conversation becomes a tool for reading the city itself

## Design Rule

Every important conversation should produce one of the following:
- a clue
- access
- reputation change
- leverage
- a direction to another NPC
- a deeper understanding of the city

If none of those are happening, the conversation should end quickly and cleanly.
