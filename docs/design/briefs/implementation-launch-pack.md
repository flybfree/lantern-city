# Lantern City — Implementation Launch Pack

This is the final handoff for starting implementation.

## What You Need

- Git repository initialized
- Python 3.12 installed
- `uv` installed
- The Lantern City docs workspace available
- The final `pyproject.toml` content
- The coding-agent tasklist

## Recommended Stack

- Python 3.12
- FastAPI
- SQLite
- SQLAlchemy 2.x
- Pydantic v2
- httpx
- pytest
- ruff
- uv
- Hatchling
- git

## Repository Setup

Use the checklist in:
- `briefs/repo-setup-checklist.md`

## Tasklist

Use the implementation tasklist in:
- `briefs/coding-agent-tasklist.md`

## Pyproject

Use the final pyproject content in:
- `backend/pyproject-toml-actual.md`

## Git Workflow

- Commit the docs baseline first.
- Commit scaffold next.
- Then implement one task per commit where possible.
- Keep tests passing before each commit.

## Core Implementation Order

1. models and serialization
2. SQLite storage
3. seed validation and city bootstrap
4. request orchestration and active slice
5. LLM interface and narrow generation tasks
6. clue / lantern / progression / case logic
7. cache invalidation and background precompute
8. minimal CLI or web shell
9. end-to-end tests

## Design Rules

- The game engine owns the world state.
- The LLM only receives the smallest relevant context.
- SQLite is sufficient for the single-player MVP.
- The city seed controls run size and complexity.
- Lazy generation keeps responses fast and bounded.

## Ready State

At this point, the design package is ready to hand to a coding agent.
The next step is implementation.
