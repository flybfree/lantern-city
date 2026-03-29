# Lantern City — Lazy Generation Pipeline

## Purpose

This pipeline defines what content should be generated at each stage of play so the system stays responsive and token usage stays controlled.

The core principle is simple:
only generate the detail the player currently needs.

## Stage 1: City Start

Generate the city seed once at the beginning of a run.

Include:
- overall city premise
- district list
- faction list
- broad lantern conditions
- starting Missingness pressure
- opening case or tension
- a few key NPC anchors
- high-level city mood

Do not generate:
- full district interiors
- every NPC in detail
- all possible scenes
- hidden outcomes for every branch

Store the seed as persistent world state.

## Stage 2: District Entry or Approach

When the player enters or moves toward a district, generate district-level detail.

Include:
- district tone
- major locations
- relevant local NPCs
- current lantern condition
- local rumors
- visible problems
- any immediate faction presence

Optional pre-generation:
- one nearby side scene
- one likely encounter
- one fallback rumor source

Do not generate:
- every hidden location
- every possible NPC motivation
- full case resolution branches

Cache the district summary once created.

## Stage 3: Scene Start

When a scene begins, generate only the immediate scene frame.

Include:
- present NPCs
- location description
- immediate tension
- any relevant clue fragments
- short-term scene objective
- scene-specific dialogue cues

Do not generate:
- long downstream consequences
- distant district changes
- unrelated lore
- branches that may never be used

## Stage 4: Interaction Expansion

As the player asks questions, investigates, or makes choices, generate only the detail needed for that branch.

Include:
- NPC responses
- clue clarifications
- evidence details
- relationship changes
- local state updates
- new redirect options if needed

This should happen incrementally, not all at once.

## Stage 5: Consequence Resolution

After a meaningful action, generate the immediate fallout.

Include:
- updated NPC state
- updated clue state
- district changes
- faction response if relevant
- case progress updates
- lantern state changes if relevant

Do not generate:
- the entire future of the city
- every faction’s full new plan
- every possible ripple effect in exhaustive detail

Only generate the consequences that are likely to matter soon.

## Stage 6: Background Expansion

While the player is engaged elsewhere, the system can precompute limited nearby content.

Possible background generation:
- the next likely district detail
- a few rumor lines
- likely NPC follow-up states
- a lightweight outline for the next plausible scene

This should be bounded and conservative.

## Cached Objects

Once generated, the following should be cached and reused:
- city seed
- district summaries
- location summaries
- NPC profiles
- current relationships
- clue records
- case state
- lantern state
- faction state

Caching prevents repeated token spending and keeps the world consistent.

## Generation Budgeting Rules

1. Generate narrow content first.
2. Expand only if the player needs it.
3. Reuse cached summaries whenever possible.
4. Do not over-generate future branches.
5. Favor short, focused expansions over giant dumps.

## Example Flow

Player starts new game:
- city seed is generated

Player enters the Old Quarter:
- Old Quarter summary is generated
- a few local NPCs are generated
- one or two likely scenes are prepared

Player talks to a shrine keeper:
- the shrine keeper’s scene detail is generated
- their response branch is expanded
- the case state updates

Player inspects a lantern:
- lantern-specific evidence details are generated on demand
- the clue is recorded
- the district state updates if needed

## Design Rule

The system should always stay one step ahead of the player, not ten steps ahead.
That keeps the world responsive, manageable, and coherent.
