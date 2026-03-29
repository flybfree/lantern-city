# Lantern City — Request Lifecycle

## Purpose

This document describes the lifecycle of a single player request in the runtime.
A request might be:
- entering a district
- talking to an NPC
- investigating a location
- making a choice
- advancing a case

The goal is to keep each request narrow, fast, and stateful.

## Lifecycle Overview

```text
Player Action
  -> UI packages the request
  -> Orchestrator identifies intent
  -> State Store loads relevant cached entities
  -> Cache Layer checks for existing summaries / branches
  -> Generator fills only missing detail
  -> Rule Engine applies consequences
  -> State Store persists updates
  -> Response Composer builds player-facing output
  -> UI renders result
```

## Step-by-Step Lifecycle

### 1. Player Action
The player chooses something in the UI:
- move somewhere
- speak to someone
- inspect something
- use leverage
- wait or observe

The UI sends a compact request.

### 2. Intent Identification
The orchestrator determines what kind of action this is.

Examples:
- district entry
- conversation
- investigation
- case progression
- fallback / generic interaction

The intent decides which data needs to be loaded.

### 3. Relevant State Load
The system loads only what is needed for the action.

Usually this includes some combination of:
- CityState
- DistrictState
- LocationState
- NPCState
- CaseState
- SceneState
- ClueState
- LanternState
- Player progression state

This should be a narrow read, not a full-world load.

### 4. Cache Check
Before generating new content, the system checks whether it already has:
- district summary
- NPC summary
- scene context
- clue summary
- prior response branch
- fallback text

If cached content exists and is still valid, reuse it.

### 5. Targeted Generation
If needed, the generator creates only the missing detail.

Examples:
- a district entry description
- an NPC’s reply to a question
- a clue clarification
- a local consequence
- a scene transition hook

Do not generate unrelated future branches at this step.

### 6. Rule Application
The rule engine evaluates consequences.

Possible updates:
- reputation changes
- access changes
- leverage gain or loss
- lantern understanding gain
- clue creation or update
- district stability shifts
- faction response changes
- case state update

This step is where the world actually changes.

### 7. Persistence
All changed state is written back to storage.

Persist:
- updated entity states
- new clues
- new summaries
- track changes
- case status changes
- any generated content worth caching

This makes the city instance durable.

### 8. Response Composition
The system assembles the player-facing result.

The response should usually include:
- what happened
- what changed
- what was learned
- what is now available
- what options the player has next

Keep this compact and readable.

### 9. UI Rendering
The UI shows the result and refreshes the current scene state.

The player should see:
- concise narrative output
- progress feedback if relevant
- any new actions or exits
- any updated track labels or summaries

## Latency Strategy

The request lifecycle should minimize wait time by:
- loading only relevant state
- reusing cached summaries
- generating only one narrow response branch
- persisting only impacted objects
- precomputing one likely next step in the background

## Example: NPC Conversation Request

```text
Player asks the foreman about the lantern outage
  -> Orchestrator classifies as conversation
  -> Load foreman NPCState + relevant case + local district state
  -> Check if foreman summary already exists
  -> Generate response to the question only
  -> Rule Engine updates trust, clue state, and maybe access
  -> Persist NPCState and clue updates
  -> Return dialogue, clue summary, and next options
```

## Example: District Entry Request

```text
Player enters the Old Quarter
  -> Orchestrator classifies as district entry
  -> Load CityState + Old Quarter DistrictState
  -> Reuse district summary if cached
  -> Generate any missing local details
  -> Rule Engine applies lantern or access effects if relevant
  -> Persist district updates
  -> Return district description + relevant NPCs + available actions
```

## Example: Investigation Request

```text
Player inspects a lantern fixture
  -> Orchestrator classifies as investigation
  -> Load LocationState + LanternState + related clues
  -> Check for existing evidence summary
  -> Generate only the needed clue detail
  -> Rule Engine updates clue reliability and lantern state
  -> Persist updated state
  -> Return findings and follow-up options
```

## Design Rule

Every request should touch only the smallest possible slice of the city.
The wider world should remain stable, cached, and ready to expand only when needed.
