# Lantern City — Generation and Token Budgeting

## Core Idea

Yes: a lot of the city can be generated lazily, as the player moves through it, rather than all at once.

This is the best way to keep wait times more consistent and avoid large token spikes.

## Design Goal

The game should feel responsive.
Instead of generating every detail for the whole city up front, the system should:
- build a small amount of structure early
- generate only what is needed for the current area or scene
- expand nearby content in the background or just-in-time
- cache results so they do not need to be regenerated repeatedly

## Recommended Generation Layers

### 1. City Seed Layer
Generated once at the start.
Contains the high-level setup:
- districts
- factions
- initial tensions
- broad lantern conditions
- starting mysteries
- key NPC anchors

This layer should be relatively compact.

### 2. District Layer
Generated when the player enters or approaches a district.
Contains:
- district tone
- local problems
- major locations
- important NPCs
- lantern condition details
- district-specific risks

### 3. Scene Layer
Generated when a scene is actually needed.
Contains:
- current NPC reactions
- immediate clue details
- current conversational state
- location-specific discovery text
- short-term consequences

### 4. Detail Layer
Generated only when the player investigates closely.
Contains:
- additional clues
- hidden state
- deeper lore
- specific witness accounts
- fine-grained object or location details

## Why This Helps

If everything is generated at once:
- token usage spikes
- latency increases
- the system may overbuild content the player never sees

If content is generated lazily:
- work is spread out more evenly
- the player sees faster responses
- the system only spends tokens on relevant content
- the city can still feel rich and reactive

## Good Places to Generate Ahead of Time

The system can safely precompute:
- the next likely district the player will enter
- nearby NPC summaries
- short rumor tables
- possible scene seeds
- fallback dialogue for common interactions

This creates smoother pacing without requiring full city simulation.

## Good Places to Generate On Demand

Generate only when needed:
- a specific NPC’s deeper motives
- a hidden room or secret route
- a scene resolution branch
- a precise clue explanation
- a case-specific revelation

This keeps token use focused on actual player action.

## Cache Strategy

Once generated, important information should be stored as persistent state.
Examples:
- district summaries
- NPC memory
- clue records
- case state
- lantern condition changes
- faction reactions

This prevents repeated regeneration and makes the city feel stable.

## Practical Rule

Do not ask the model to generate the entire city at maximum detail on turn one.
Instead:
- create the scaffold first
- fill in detail as the player approaches it
- reuse cached state wherever possible
- keep each generation step small and relevant

## Player Experience Goal

The player should feel like the city is alive and unfolding, not like the system is pausing to invent everything from scratch.

That means generation should happen:
- before the player notices a delay whenever possible
- in small, bounded chunks
- with stable cached summaries behind the scenes

## Design Rule

Generate only as much as the current moment needs.
Let the city reveal itself in layers as the player moves through it.
