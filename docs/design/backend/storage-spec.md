# Lantern City — Storage Specification

## Goal

Persist the city instance, player progress, generated content, and cached summaries so the game can continue across sessions and only generate detail when needed.

## Recommended Approach

For the MVP, use SQLite as the durable store.

Why SQLite for MVP:
- simple deployment
- zero infrastructure overhead
- easy local testing
- sufficient for a single-player narrative system

If the game later becomes multi-user or networked, the same logical schema can move to Postgres with minimal changes.

## Storage Model

Use two layers:

### 1. Durable state tables
These store the source of truth.
Examples:
- city seed
- city state
- district state
- location state
- npc state
- faction state
- lantern state
- case state
- scene state
- clue state
- player progression state

### 2. Cache tables
These store generated summaries and narrow expansions.
Examples:
- district summary cache
- npc summary cache
- location summary cache
- scene summary cache
- generated response cache
- next-step precompute cache

## Data Organization

Each object should have:
- id
- type
- version
- created_at
- updated_at
- serialized JSON payload

A practical schema is one table per object type, or one generic `objects` table with a `type` column.

### Recommended MVP choice
Use one generic table plus JSON payload for speed of implementation:

Table: `world_objects`
- `id` TEXT PRIMARY KEY
- `type` TEXT NOT NULL
- `version` INTEGER NOT NULL
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL
- `payload` TEXT NOT NULL

Table: `cache_entries`
- `cache_key` TEXT PRIMARY KEY
- `object_type` TEXT NOT NULL
- `object_id` TEXT
- `version` INTEGER NOT NULL
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL
- `payload` TEXT NOT NULL
- `ttl_seconds` INTEGER NULL

This keeps the MVP simple while still supporting structured persistence.

## Object Persistence Rules

### Persistent objects
These must always survive across sessions:
- CitySeed
- CityState
- DistrictState
- LocationState
- NPCState
- FactionState
- LanternState
- CaseState
- SceneState
- ClueState
- PlayerProgressState

### Cacheable objects
These can be regenerated if needed, but should usually be stored:
- district summaries
- location summaries
- NPC summaries
- case summaries
- generated scene text
- generated responses
- precomputed next-step content

## Versioning Rules

Every object should have a version number.
Increment version whenever the object changes.

Use versioning to:
- detect stale cached summaries
- invalidate dependent generated content
- support future migrations

Example:
- DistrictState changes -> district summary cache invalidates
- NPCState changes -> NPC response cache invalidates
- LanternState changes -> location and clue caches may invalidate

## Suggested Relationships

The store should support references by ID, not deep nesting.

Example:
- CityState lists district IDs
- DistrictState lists location IDs and NPC IDs
- NPCState references clue IDs and relationship flags
- CaseState references district IDs, NPC IDs, and clue IDs

This avoids large rewrites when one object changes.

## Loading Strategy

When handling a request, load only:
- the active working set
- the directly relevant persistent objects
- any dependent cache entries

Do not load the full world graph unless the action truly needs it.

## Save Strategy

After a request:
1. update only changed objects
2. increment their version numbers
3. write them back to storage
4. update any affected caches
5. invalidate stale dependent cache entries

## Cache Invalidation Rules

Invalidate caches when:
- the source object version changes
- lantern condition changes
- case status changes
- NPC trust/suspicion changes
- district stability changes
- clue reliability changes

## Backup and Recovery

For MVP, the database file itself is the durable backup.

Minimum expected behavior:
- safe on normal shutdown
- recoverable on restart
- robust enough for a single-player session-based game

Later, add periodic export snapshots if desired.

## Minimal API to the Storage Layer

The storage module should support at least:
- `save_object(obj)`
- `load_object(type, id)`
- `list_objects(type)`
- `delete_object(type, id)`
- `save_cache(key, payload, version)`
- `load_cache(key)`
- `invalidate_cache(prefix_or_id)`

## Design Rule

Storage should be boring and reliable.
If the data model changes often, the store should not need a redesign.
