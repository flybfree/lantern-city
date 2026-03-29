# Lantern City — Implementation-Oriented Spec

## Purpose

This document translates the design into an implementation shape.
It focuses on:
- what data gets stored
- what gets generated when
- what must be cached
- how state changes flow through the system
- how to keep token usage and latency bounded

## Core Runtime Model

The game should treat Lantern City as a persistent world instance with layered generated content.

Recommended runtime objects:
- CitySeed
- CityState
- DistrictState
- LocationState
- NPCState
- CaseState
- SceneState
- ClueState
- FactionState
- LanternState

The system should generate details lazily and cache them after generation.

## Primary Data Structures

### CitySeed
The starting configuration for a run.
Generated once, then stored permanently for that run.

Suggested fields:
- city_id
- seed_prompt
- city_premise
- dominant_mood
- district_ids
- faction_ids
- starting_cases
- initial_missingness_pressure
- initial_lantern_profile
- key_npc_ids
- generation_timestamp

### CityState
The persistent top-level world state.

Suggested fields:
- city_id
- current_day / turn / time index
- global tension
- civic trust
- missingness pressure
- player presence level
- active_case_ids
- district_state_refs
- faction_state_refs
- summary_cache

### DistrictState
Represents one district instance.

Suggested fields:
- district_id
- name
- tone
- stability
- lantern_condition
- governing_power
- active_problems
- visible_locations
- hidden_locations
- relevant_npc_ids
- rumor_pool
- current_access_level
- summary_cache
- last_updated_at

### LocationState
Represents a specific place inside a district.

Suggested fields:
- location_id
- district_id
- name
- type
- access_state
- description_cache
- known_npcs
- hidden_features
- clues_present
- lantern_effects
- last_updated_at

### NPCState
Represents one tracked NPC.

Suggested fields:
- npc_id
- name
- role_category
- district_id
- location_id
- public_identity
- hidden_objective
- current_objective
- trust_in_player
- fear
- suspicion
- loyalty
- known_clues
- known_promises
- relationship_flags
- memory_log
- relevance_rating
- last_updated_at

### FactionState
Represents one faction’s current posture.

Suggested fields:
- faction_id
- name
- public_goal
- hidden_goal
- influence_by_district
- tension_with_other_factions
- attitude_toward_player
- known_assets
- known_losses
- active_plans
- summary_cache

### LanternState
Represents the lantern condition for a district or specific site.

Suggested fields:
- lantern_id
- scope_type (district / street / site)
- scope_id
- owner_faction
- maintainer_faction_or_group
- condition_state (bright / dim / flickering / extinguished / altered)
- reach_radius_or_scope_notes
- social_effects
- memory_effects
- access_effects
- anomaly_flags
- last_updated_at

### CaseState
Represents one active investigation or story arc.

Suggested fields:
- case_id
- title
- case_type
- status (active / stalled / escalated / solved / partially_solved / failed)
- involved_district_ids
- involved_npc_ids
- involved_faction_ids
- known_clues
- open_questions
- objective_summary
- resolution_summary
- fallout_summary
- last_updated_at

### SceneState
Represents a single active interaction unit.

Suggested fields:
- scene_id
- case_id
- scene_type
- location_id
- participating_npc_ids
- immediate_goal
- current_prompt_state
- scene_clues
- scene_tension
- scene_outcome
- last_updated_at

### ClueState
Represents one clue or evidence item.

Suggested fields:
- clue_id
- source_type
- source_id
- clue_text
- reliability
- tags
- related_npc_ids
- related_case_ids
- related_district_ids
- status (new / confirmed / contradicted / obsolete)
- last_updated_at

## Generation Triggers

### On New Game
Generate:
- CitySeed
- initial CityState
- first-wave DistrictState summaries
- key NPC anchors
- opening CaseState

Do not generate full detail for every district, NPC, or location.

### On District Entry
Generate or expand:
- DistrictState summary
- 3 to 5 relevant locations
- district rumors
- relevant NPC summaries
- district lantern state

### On Location Entry
Generate or expand:
- LocationState details
- immediate clues present
- local NPC reactions
- scene framing if needed

### On NPC Interaction
Generate or expand:
- NPCState response branch
- conversation-specific clues
- relationship update
- access/reputation/leverage updates
- redirect options to other NPCs

### On Case Advancement
Generate or expand:
- next scene candidates
- updated clue connections
- faction reactions
- district fallout
- case status changes

### On Lantern Change
Generate or expand:
- local social consequences
- memory/testimony shifts
- access changes
- clue reliability shifts
- district stability change

## Caching Rules

Cache permanently within the run:
- seed data
- district summaries
- location summaries
- NPC summaries
- faction summaries
- clue records
- case state
- lantern state
- player progression state

Regenerate only when state changes or when the player needs deeper detail.

## Lazy Generation Rule Set

1. Generate the scaffold first.
2. Expand only the part the player is entering now.
3. Keep current scene generation narrow.
4. Cache the result.
5. Reuse cached summaries instead of re-generating.
6. Precompute only one likely step ahead.

## Suggested Persistence Layer

A simple implementation could use a document store or key-value store with IDs for each entity.

Example organization:
- city/<city_id>/seed
- city/<city_id>/state
- city/<city_id>/districts/<district_id>
- city/<city_id>/locations/<location_id>
- city/<city_id>/npcs/<npc_id>
- city/<city_id>/factions/<faction_id>
- city/<city_id>/cases/<case_id>
- city/<city_id>/clues/<clue_id>

## Update Flow

When the player acts:
1. load current scene and related cached state
2. generate only the immediate needed response
3. apply state updates
4. persist updated objects
5. return a concise player-facing result

## Recommended In-Memory Model

For runtime efficiency, keep a small active set in memory:
- current city summary
- current district
- current location
- current scene
- active case
- active NPCs in scene
- relevant clues

Everything else can stay cached on disk or in a database until needed.

## Player-Facing Feedback

After important updates, show a short summary of what changed.
Examples:
- new clue discovered
- reputation changed
- access changed
- lantern condition changed
- case advanced

The player should always feel the city state moving, even if the backend is only making small updates.

## Performance Goal

The system should maintain consistent response times by:
- limiting each generation step
- avoiding full-city regeneration
- caching aggressively
- precomputing only nearby content
- keeping future branches abstract until needed

## Design Rule

The game should always operate on a small active slice of the city and a larger cached world behind it.
That is the best way to preserve both responsiveness and persistence.
