# Lantern City — Backend Overview

## Purpose

This document ties together storage, generation, request handling, and caching.

## Backend Responsibilities

The backend should:
- hold the persistent city instance
- load only the active slice of state for each request
- call the LLM only when narrow generation is needed
- update state and versioning
- persist and cache results
- return a compact player-facing response

## Core Components

### 1. Orchestrator
Determines what type of player request occurred and which objects need loading.

### 2. Store
Persists world objects, progression state, and case state.

### 3. Cache
Stores generated summaries and response text.

### 4. Generator
Makes narrow LLM calls for city seeds, districts, NPC responses, clues, and fallout.

### 5. Rule Engine
Applies game logic and updates state based on player actions and generated results.

### 6. Response Composer
Turns updated state into a concise UI response.

## Request Flow

1. Player submits an action.
2. Orchestrator classifies the request.
3. Store loads relevant objects.
4. Cache is checked.
5. Generator fills missing detail if needed.
6. Rule Engine applies updates.
7. Store persists changed objects.
8. Cache is refreshed or invalidated.
9. Response Composer builds the output.
10. UI renders the result.

## Long-Term Storage Strategy

The backend should use persistent storage for:
- city seed and city state
- all tracked NPCs
- districts and locations
- cases and clues
- progression state
- lantern state
- caches of generated summaries

For MVP, SQLite is the best fit.

## LLM Strategy

The backend should use a provider-agnostic generation layer.
The game should be able to run against:
- local LM Studio
- OpenAI-compatible cloud API
- future compatible backends

## Bounded Generation Strategy

Generation should happen in layers:
- seed at startup
- district on entry
- scene on demand
- NPC response on demand
- fallout on state change
- next-step background precompute only one step ahead

## What Must Be Implemented Before Coding the MVP

1. Storage schema
2. Serialization model
3. Generation interface
4. Request lifecycle
5. Cache invalidation rules
6. State transition rules

## Design Rule

If the backend can’t answer three questions cleanly, it is not ready for code:
- What state is persistent?
- What content is cached?
- What gets generated now versus later?
