# Lantern City — Replayability and City Seeds

## Core Idea

Each new game should begin with a procedurally or LLM-generated city seed.
That seed defines a unique initial state for the Lantern City instance.

Once the seed is created, that city becomes a persistent world instance.
The player and NPC agents then evolve that specific city over the course of the campaign.

## Why This Works

This supports replayability while preserving continuity.
Every new run can feel like a different Lantern City, but once play begins:
- district states remain consistent
- faction relationships persist
- NPC memory matters
- lantern conditions evolve naturally
- player choices accumulate into a distinct history

## City Seed Components

A city seed should define the starting conditions for:
- district stability
- lantern condition by district
- faction alignment
- key NPC relationships
- initial mysteries
- civic tension
- Missingness pressure
- resource scarcity or abundance
- dominant mood and social climate

## Seed Generation Approach

The LLM can be used to generate a new city seed from a structured prompt.
That prompt should request:
- a coherent core premise
- 3 to 6 initial tensions
- a few faction conflicts
- one or two central mysteries
- a distinct lantern pattern
- a tonal variation from previous runs

The result should not be random chaos.
It should be a coherent configuration with internal logic.

## Persistent City Instance

After creation, the city should behave like a living simulation.
The same world instance should keep track of:
- where lanterns have changed
- which NPCs remember what
- which districts have become unstable
- what secrets have been uncovered
- which factions have adapted to the player

This makes the campaign feel like a city that exists independently of the player’s interface.

## Replayability Benefits

This design gives the game:
- variety across runs
- different mystery structures
- different faction tensions
- different lantern politics
- different early-game problems
- different emotional textures

It also makes discovery more meaningful because the player cannot memorize one fixed city layout.

## Design Rule

The city seed creates the world.
The campaign evolves the world.
The player’s job is to uncover what kind of city this specific instance has become.
