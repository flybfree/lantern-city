# Lantern City — API Contract Draft

## Purpose

This draft defines the minimal backend API surface needed by the MVP.

## Suggested Endpoints

### POST /api/new-game
Creates a new city seed and initializes persistent world state.

Request:
- optional seed parameters

Response:
- city id
- initial district ids
- initial case id
- player progress state

### POST /api/request
Handles a single player action.

Request:
- player request object

Response:
- narrative text
- state updates
- next actions
- changed track values

### GET /api/state/current
Returns the current active slice of the city.

Response:
- city summary
- current district
- current location
- active scene
- active case
- visible NPCs
- relevant clues

### GET /api/state/object/{type}/{id}
Returns a stored world object by type and id.

### POST /api/cache/precompute
Triggers lazy background generation for one likely next step.

### POST /api/debug/reset
Resets a development session.

## API Design Rules

- Keep requests small.
- Return structured JSON.
- Do not expose the entire world when only the active slice is needed.
- Separate persistent state from generated text.

## MVP Priority

Only the first two endpoints are strictly required for the first playable version:
- `/api/new-game`
- `/api/request`

The rest can follow once the backend structure is stable.
