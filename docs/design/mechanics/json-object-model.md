# Lantern City — JSON Object Model

## Purpose

This document defines the runtime JSON objects for the lazy-generation system and request lifecycle.

The goal is to have a concrete, implementation-friendly model for:
- persistent world state
- cached generated summaries
- active scene slices
- player requests
- generator outputs
- state updates

## Design Principles

- Keep the persistent world separate from transient request data.
- Store summaries and generated text in cacheable objects.
- Keep the active slice small.
- Use stable IDs everywhere.
- Update only the objects impacted by a request.

## Common Conventions

All major objects should include:
- `id`: unique stable identifier
- `type`: object type label
- `created_at`: timestamp or turn index
- `updated_at`: timestamp or turn index
- `version`: integer incremented on update

## 1. City Seed

Represents the initial city instance created at game start.

```json
{
  "id": "cityseed_001",
  "type": "CitySeed",
  "version": 1,
  "created_at": "turn_0",
  "updated_at": "turn_0",
  "city_premise": "A rain-soaked port city where lanterns stabilize memory and civic order.",
  "dominant_mood": ["noir", "wet", "uncertain"],
  "district_ids": ["district_old_quarter", "district_docks", "district_lantern_ward"],
  "faction_ids": ["faction_council_lights", "faction_memory_keepers"],
  "starting_cases": ["case_missing_clerk"],
  "initial_missingness_pressure": 0.35,
  "initial_lantern_profile": {
    "district_old_quarter": "dim",
    "district_docks": "flickering",
    "district_lantern_ward": "bright"
  },
  "key_npc_ids": ["npc_shrine_keeper", "npc_dock_foreman"]
}
```

## 2. City State

The persistent top-level world state.

```json
{
  "id": "city_001",
  "type": "CityState",
  "version": 12,
  "created_at": "turn_0",
  "updated_at": "turn_27",
  "city_seed_id": "cityseed_001",
  "time_index": 27,
  "global_tension": 0.62,
  "civic_trust": 0.44,
  "missingness_pressure": 0.51,
  "active_case_ids": ["case_missing_clerk"],
  "district_ids": ["district_old_quarter", "district_docks", "district_lantern_ward"],
  "faction_ids": ["faction_council_lights", "faction_memory_keepers"],
  "player_presence_level": 0.31,
  "summary_cache": {
    "short": "The city is tense and slightly unstable.",
    "long": "Lantern state is diverging between districts; civic trust is weak in the Old Quarter."
  }
}
```

## 3. District State

Represents a district instance.

```json
{
  "id": "district_old_quarter",
  "type": "DistrictState",
  "version": 8,
  "created_at": "turn_0",
  "updated_at": "turn_27",
  "name": "Old Quarter",
  "tone": "ancient, damp, memory-heavy",
  "stability": 0.47,
  "lantern_condition": "dim",
  "governing_power": "faction_memory_keepers",
  "active_problems": ["missing_records", "lantern_outage"],
  "visible_locations": ["location_archive_steps", "location_shrine_lane"],
  "hidden_locations": ["location_subarchive"] ,
  "relevant_npc_ids": ["npc_shrine_keeper", "npc_archive_clerk"],
  "rumor_pool": [
    "Someone edited a family from the ledger.",
    "The shrine lamps are being relit at odd hours."
  ],
  "current_access_level": "restricted",
  "summary_cache": {
    "short": "The Old Quarter feels stale and uncertain.",
    "long": "Old stone, failing lanterns, and disputed records make the district feel like it is forgetting itself."
  },
  "last_updated_at": "turn_27"
}
```

## 4. Location State

Represents one place inside a district.

```json
{
  "id": "location_archive_steps",
  "type": "LocationState",
  "version": 4,
  "created_at": "turn_0",
  "updated_at": "turn_27",
  "district_id": "district_old_quarter",
  "name": "Archive Steps",
  "location_type": "public_record_site",
  "access_state": "restricted",
  "known_npc_ids": ["npc_archive_clerk"],
  "hidden_feature_ids": ["feature_false_wall"],
  "clue_ids": ["clue_missing_family_entry"],
  "lantern_effects": {
    "memory_stability": 0.38,
    "route_certainty": 0.52
  },
  "description_cache": {
    "short": "Stone steps leading to a public archive entrance.",
    "long": "The steps are damp and worn, with a lamp that burns too softly to fully illuminate the entry."
  },
  "last_updated_at": "turn_27"
}
```

## 5. NPC State

Represents a tracked NPC.

```json
{
  "id": "npc_shrine_keeper",
  "type": "NPCState",
  "version": 6,
  "created_at": "turn_0",
  "updated_at": "turn_27",
  "name": "Ila Venn",
  "role_category": "informant",
  "district_id": "district_old_quarter",
  "location_id": "location_shrine_lane",
  "public_identity": "shrine keeper",
  "hidden_objective": "protect a ritual alteration from discovery",
  "current_objective": "send the player toward the archive clerk",
  "trust_in_player": 0.56,
  "fear": 0.21,
  "suspicion": 0.33,
  "loyalty": "shrine_circle",
  "known_clue_ids": ["clue_missing_family_entry"],
  "known_promises": ["promise_guidance_to_archive"],
  "relationship_flags": ["hesitant", "useful"],
  "memory_log": [
    {
      "turn": 23,
      "event": "Spoke to player about lantern outages."
    }
  ],
  "relevance_rating": 0.74,
  "last_updated_at": "turn_27"
}
```

## 6. Faction State

Represents a faction’s current posture.

```json
{
  "id": "faction_memory_keepers",
  "type": "FactionState",
  "version": 5,
  "created_at": "turn_0",
  "updated_at": "turn_27",
  "name": "Memory Keepers",
  "public_goal": "preserve records and continuity",
  "hidden_goal": "control what the city is allowed to remember",
  "influence_by_district": {
    "district_old_quarter": 0.78,
    "district_docks": 0.22
  },
  "tension_with_other_factions": {
    "faction_council_lights": 0.58
  },
  "attitude_toward_player": "wary",
  "known_assets": ["archives", "clerks"],
  "known_losses": ["ledger_sabotage"],
  "active_plans": ["stabilize old records"],
  "summary_cache": {
    "short": "They want control over continuity.",
    "long": "The Memory Keepers present themselves as archivists, but they also decide which facts survive."
  }
}
```

## 7. Lantern State

Represents a lantern or lantern system.

```json
{
  "id": "lantern_old_quarter_01",
  "type": "LanternState",
  "version": 9,
  "created_at": "turn_0",
  "updated_at": "turn_27",
  "scope_type": "district",
  "scope_id": "district_old_quarter",
  "owner_faction": "faction_council_lights",
  "maintainer_group": "faction_shrine_circle",
  "condition_state": "dim",
  "reach_scope_notes": "Influence appears strongest within two blocks of the archive.",
  "social_effects": ["hesitation", "low_visibility"],
  "memory_effects": ["inconsistent testimony"],
  "access_effects": ["restricted movement after dark"],
  "anomaly_flags": ["possible_tampering"],
  "last_updated_at": "turn_27"
}
```

## 8. Case State

Represents a case or quest arc.

```json
{
  "id": "case_missing_clerk",
  "type": "CaseState",
  "version": 7,
  "created_at": "turn_0",
  "updated_at": "turn_27",
  "title": "The Missing Clerk",
  "case_type": "mystery",
  "status": "active",
  "involved_district_ids": ["district_old_quarter", "district_lantern_ward"],
  "involved_npc_ids": ["npc_shrine_keeper", "npc_archive_clerk"],
  "involved_faction_ids": ["faction_memory_keepers"],
  "known_clue_ids": ["clue_missing_family_entry"],
  "open_questions": [
    "Who removed the clerk from the records?",
    "Was the lantern altered intentionally?"
  ],
  "objective_summary": "Determine why the clerk and associated records have vanished.",
  "resolution_summary": null,
  "fallout_summary": null,
  "last_updated_at": "turn_27"
}
```

## 9. Scene State

Represents the current active scene.

```json
{
  "id": "scene_014",
  "type": "SceneState",
  "version": 3,
  "created_at": "turn_27",
  "updated_at": "turn_27",
  "case_id": "case_missing_clerk",
  "scene_type": "conversation",
  "location_id": "location_shrine_lane",
  "participating_npc_ids": ["npc_shrine_keeper"],
  "immediate_goal": "learn whether the lantern outage is connected to the missing clerk",
  "current_prompt_state": "awaiting_player_question",
  "scene_clue_ids": ["clue_missing_family_entry"],
  "scene_tension": 0.42,
  "scene_outcome": null,
  "last_updated_at": "turn_27"
}
```

## 10. Clue State

Represents one clue.

```json
{
  "id": "clue_missing_family_entry",
  "type": "ClueState",
  "version": 2,
  "created_at": "turn_22",
  "updated_at": "turn_27",
  "source_type": "document",
  "source_id": "archive_registry_page_11",
  "clue_text": "A family entry appears and disappears across different ledger copies.",
  "reliability": "contradicted",
  "tags": ["records", "memory", "lantern", "missingness"],
  "related_npc_ids": ["npc_shrine_keeper", "npc_archive_clerk"],
  "related_case_ids": ["case_missing_clerk"],
  "related_district_ids": ["district_old_quarter"],
  "status": "new",
  "last_updated_at": "turn_27"
}
```

## 11. Player Progress State

Represents tracked progression values.

```json
{
  "id": "player_progress_001",
  "type": "PlayerProgressState",
  "version": 10,
  "created_at": "turn_0",
  "updated_at": "turn_27",
  "lantern_understanding": {
    "score": 32,
    "tier": "Informed"
  },
  "access": {
    "score": 21,
    "tier": "Restricted"
  },
  "reputation": {
    "score": 18,
    "tier": "Wary"
  },
  "leverage": {
    "score": 26,
    "tier": "Useful"
  },
  "city_impact": {
    "score": 14,
    "tier": "Local"
  },
  "clue_mastery": {
    "score": 41,
    "tier": "Competent"
  }
}
```

## 12. Player Request Object

This is the runtime request sent from UI to the orchestrator.

```json
{
  "id": "req_1001",
  "type": "PlayerRequest",
  "version": 1,
  "timestamp": "turn_27",
  "player_id": "player_001",
  "intent": "talk_to_npc",
  "target_id": "npc_shrine_keeper",
  "location_id": "location_shrine_lane",
  "case_id": "case_missing_clerk",
  "scene_id": "scene_014",
  "input_text": "Ask about the lantern outage.",
  "context_refs": {
    "district_id": "district_old_quarter",
    "clue_ids": ["clue_missing_family_entry"]
  }
}
```

## 13. Generation Job Object

Represents a lazy generation task.

```json
{
  "id": "genjob_2001",
  "type": "GenerationJob",
  "version": 1,
  "created_at": "turn_27",
  "updated_at": "turn_27",
  "job_kind": "npc_response",
  "priority": "high",
  "status": "queued",
  "input_refs": {
    "npc_id": "npc_shrine_keeper",
    "case_id": "case_missing_clerk",
    "scene_id": "scene_014"
  },
  "required_outputs": ["dialogue", "clue_update", "relationship_delta"],
  "cached_output_id": null
}
```

## 14. Generated Output Object

Represents a generated response or summary.

```json
{
  "id": "genout_3001",
  "type": "GeneratedOutput",
  "version": 1,
  "created_at": "turn_27",
  "updated_at": "turn_27",
  "source_job_id": "genjob_2001",
  "output_kind": "npc_response",
  "text": "The shrine keeper lowers their voice and says the outage started before the clerk vanished.",
  "structured_updates": {
    "clue_ids_created": ["clue_outage_before_disappearance"],
    "npc_relationship_delta": {
      "npc_id": "npc_shrine_keeper",
      "trust_change": 0.08
    }
  }
}
```

## 15. Response Object

Represents the final player-facing response.

```json
{
  "id": "resp_4001",
  "type": "PlayerResponse",
  "version": 1,
  "created_at": "turn_27",
  "updated_at": "turn_27",
  "request_id": "req_1001",
  "narrative_text": "The shrine keeper lowers their voice and says the outage started before the clerk vanished.",
  "state_changes": [
    {
      "type": "clue_added",
      "clue_id": "clue_outage_before_disappearance"
    },
    {
      "type": "npc_trust_change",
      "npc_id": "npc_shrine_keeper",
      "delta": 0.08
    }
  ],
  "next_actions": [
    "Ask about the archive records",
    "Inspect the lantern",
    "Leave the conversation"
  ]
}
```

## 16. Active Working Set Object

This is the small slice of the city kept hot in memory.

```json
{
  "id": "active_slice_001",
  "type": "ActiveWorkingSet",
  "version": 1,
  "created_at": "turn_27",
  "updated_at": "turn_27",
  "city_id": "city_001",
  "district_id": "district_old_quarter",
  "location_id": "location_shrine_lane",
  "case_id": "case_missing_clerk",
  "scene_id": "scene_014",
  "npc_ids": ["npc_shrine_keeper"],
  "clue_ids": ["clue_missing_family_entry"],
  "cached_summaries": {
    "district": "The Old Quarter feels stale and uncertain.",
    "location": "A shrine lane with a softly glowing lantern and damp stone.",
    "scene": "The shrine keeper is willing to talk, but carefully."
  }
}
```

## 17. Recommended Update Flow

A typical request should do this:

1. Load the active working set.
2. Load the relevant persistent objects.
3. Check for cached summaries or outputs.
4. Generate only the missing narrow content.
5. Create or update state objects.
6. Persist the changed objects.
7. Write a response object.
8. Refresh the active working set.

## 18. Implementation Notes

- Treat summaries as cacheable generated fields, not source of truth.
- Treat structured state fields as the source of truth.
- Keep each generated object small enough to avoid unnecessary token cost.
- Store relationship deltas and clue updates explicitly, not only in prose.
- Use object versioning so cached content can be invalidated when state changes.

## 19. Design Rule

The JSON model should let the system generate just enough, update just enough, and cache everything useful.
That is what keeps Lantern City persistent, responsive, and affordable to run.
