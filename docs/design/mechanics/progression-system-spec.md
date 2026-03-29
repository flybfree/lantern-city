# Lantern City — Progression System Spec

## Purpose

This document defines how progression tracks increase, how NPC types feed them, and how the game should show progress to the player.

The goal is to make progression feel concrete, readable, and tied to real changes in play.

## Recommended Progression Model

Use tiered tracks instead of traditional numeric leveling.

Each major track should have 5 tiers:
- Tier 1: Novice / Limited
- Tier 2: Informed / Emerging
- Tier 3: Competent / Useful
- Tier 4: Advanced / Strong
- Tier 5: Expert / Dominant

This works well for Lantern City because the game is about insight, access, and influence rather than combat stats.

## Track Thresholds

The exact numbers can be tuned, but a good default is 100 points per track, divided across the tiers.

Suggested thresholds:
- Tier 1: 0–19
- Tier 2: 20–39
- Tier 3: 40–59
- Tier 4: 60–79
- Tier 5: 80–100

A track should only increase when the player has done something that changes state.

## Track Definitions

### 1. Lantern Understanding
Increases when the player learns something real about lanterns.

Gains:
- small gain for observing patterns
- medium gain for identifying tampering or control
- larger gain for uncovering a lantern’s reach or true function
- major gain for solving a lantern-related mystery or ritual mechanism

Unlocks:
- better interpretation of lantern states
- lantern-specific investigation options
- ability to distinguish damage from manipulation
- expert-level lantern actions at higher tiers

### 2. Access
Increases when the player is allowed into new places or social circles.

Gains:
- small gain for being admitted once
- medium gain for repeated entry or introduction
- large gain for being trusted with private spaces
- major gain for secret routes or restricted systems

Unlocks:
- new districts
- private rooms
- archives
- rituals
- faction interiors
- hidden routes

### 3. Reputation
Increases when groups view the player favorably or respectfully.

Gains:
- small gain for helping someone locally
- medium gain for solving a district problem
- larger gain for public success or visible loyalty
- major gain for faction-wide recognition

Unlocks:
- more cooperative dialogue
- fewer resistance checks
- access through goodwill
- alternate solutions to social problems

### 4. Leverage
Increases when the player obtains usable pressure points.

Gains:
- small gain for discovering a useful secret
- medium gain for finding contradiction or evidence
- larger gain for earning a favor or debt
- major gain for uncovering a decisive hidden truth

Unlocks:
- forcing meetings
- changing testimony
- bypassing obstruction
- resolving conflicts without direct confrontation

### 5. City Impact
Increases when the player’s actions begin to alter larger patterns.

Gains:
- small gain when an NPC changes behavior because of the player
- medium gain when a faction reacts to the player
- larger gain when a district state changes because of player action
- major gain when the player changes the balance of a citywide conflict

Unlocks:
- larger-scale decisions
- visible consequences across multiple districts
- NPCs adapting their plans to the player
- structural shifts in the city

### 6. Clue Mastery
Increases when the player becomes better at reading information.

Gains:
- small gain for spotting useful contradiction
- medium gain for connecting clues across scenes
- larger gain for correctly identifying a hidden pattern
- major gain for solving a complex mystery structure

Unlocks:
- stronger clue summaries
- more reliable inference options
- better recognition of missing information
- higher confidence in interpreting uncertain evidence

## How NPC Categories Feed Tracks

### Lead NPCs
Primarily feed:
- Access
- Leverage
- City Impact
- Lantern Understanding
- Clue Mastery

They should usually produce real advancement.

### Informants
Primarily feed:
- Clue Mastery
- Lantern Understanding
- Access
- small Reputation gains

They often redirect the player toward useful leads.

### World NPCs
Primarily feed:
- Reputation
- Clue Mastery
- minor Access

They make the district feel alive and help the player understand local context.

### Ambient NPCs
Usually feed:
- atmosphere only
- occasional tiny Reputation or Clue Mastery gains if a meaningful exchange occurs

They should not dominate progression.

## Progression Gain Guidelines

A conversation or action should grant progression only if it causes one of these:
- reveals a new fact
- changes a relationship
- opens access
- creates leverage
- improves lantern understanding
- changes the city state

Suggested gain sizes:
- minor discovery: 2–5 points
- useful clue or access: 5–10 points
- major insight or relationship shift: 10–20 points
- case-defining breakthrough: 20+ points

The exact values can be tuned, but gains should feel meaningful and not spammy.

## UI Feedback Model

The player should always know when progress happened, even if the underlying numbers stay hidden.

### Immediate feedback after a meaningful interaction
Show a short summary like:
- “Lantern Understanding increased.”
- “You gained access to the archive.”
- “The foreman now trusts you.”
- “You earned leverage over the dock office.”
- “The city has begun reacting to your presence.”

### Optional detailed feedback
For players who want clarity, show a more explicit breakdown:
- track name
- tier progress
- what caused the gain
- what it unlocked

Example:
- Lantern Understanding +8
- Reason: identified lantern tampering in the Old Quarter
- New tier progress: 32 / 40

### Best practice
Do not overwhelm the player with raw numbers every time unless they want that mode.
Use short natural language by default and more explicit detail in a journal or status screen.

## Recommended Status Screen

A good progress display could show:
- Lantern Understanding: Informed
- Access: Restricted
- Reputation: Wary
- Leverage: Limited
- City Impact: Local
- Clue Mastery: Competent

This gives the player a clear sense of growth without turning the game into a spreadsheet.

## Design Rule

If the player can point to a concrete new capability, a track should have increased.
If nothing changed in what they can know, do, or influence, then it was not progression.
