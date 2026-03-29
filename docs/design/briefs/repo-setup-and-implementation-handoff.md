# Lantern City — Repo Setup and Implementation Handoff

This document is the practical handoff for starting the Lantern City MVP repository and implementation.

## 1. Recommended Tech Stack

- Python 3.12
- FastAPI
- SQLite
- SQLAlchemy 2.x
- Pydantic v2
- httpx
- pytest
- ruff
- uv
- git

## 2. Repository Structure

Use this layout:

```text
lantern-city/
├── pyproject.toml
├── README.md
├── .gitignore
├── src/
│   └── lantern_city/
│       ├── __init__.py
│       ├── app.py
│       ├── cli.py
│       ├── models.py
│       ├── serialization.py
│       ├── store.py
│       ├── seed_schema.py
│       ├── orchestrator.py
│       ├── active_slice.py
│       ├── engine.py
│       ├── response.py
│       ├── cache.py
│       ├── background.py
│       ├── progression.py
│       ├── cases.py
│       ├── clues.py
│       ├── lanterns.py
│       ├── llm_client.py
│       ├── bootstrap.py
│       └── generation/
│           ├── __init__.py
│           ├── city_seed.py
│           ├── district.py
│           ├── npc_response.py
│           └── fallout.py
├── tests/
└── docs/
```

## 3. Git Bootstrap

### Initialize repository

```bash
mkdir -p ~/lantern-city
cd ~/lantern-city
git init
```

### Add ignore rules

Use the drafted `.gitignore` rules from:
- `~/lantern-city-docs/backend/gitignore-draft.txt`

### First commit

Commit the design and backend docs first:

```bash
git add README.md pyproject.toml .gitignore docs/
git commit -m "docs: add Lantern City design and backend specs"
```

## 4. Dependency Setup

Suggested `pyproject.toml` foundation:
- runtime: fastapi, uvicorn, sqlalchemy, pydantic, httpx
- dev: pytest, pytest-asyncio, ruff

Using `uv`:

```bash
uv venv
source .venv/bin/activate
uv add fastapi uvicorn sqlalchemy pydantic httpx
uv add --dev pytest pytest-asyncio ruff
```

## 5. Implementation Order

Recommended order:
1. Core models and serialization
2. SQLite persistence
3. Seed validation
4. Seed generation
5. Bootstrap
6. Request orchestration and active slice
7. LLM interface and generation functions
8. Clue, lantern, progression, and case logic
9. Cache invalidation and background precompute
10. Minimal CLI or web shell
11. End-to-end tests

## 6. Coding Agent Tasklist Location

Use this file for the implementation handoff:
- `briefs/coding-agent-tasklist.md`

## 7. Key Design Rules

- The game engine owns all world state.
- The LLM only receives narrow context and returns narrow structured output.
- SQLite is sufficient for the single-player MVP.
- Lazy generation should keep only one step ahead of the player.
- Every meaningful state change must persist.

## 8. What Is Ready Now

The following are defined well enough to begin implementation:
- city seed parameter groups
- JSON seed schema
- storage strategy
- LLM interface strategy
- request lifecycle and orchestration
- progression tracks
- case and scene structure
- NPC interaction model
- MVP scope
- coding-agent tasklist

## 9. Suggested Next Step

Start with Phase 1 of the coding-agent tasklist:
- models
- serialization
- SQLite store

Then proceed in order.
