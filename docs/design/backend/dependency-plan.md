# Lantern City — Dependency Plan

## Goal

Choose a lean set of dependencies that support the MVP backend without overbuilding.

## Recommended Dependencies

### Runtime
- Python 3.12
- fastapi
- uvicorn
- sqlalchemy
- pydantic
- httpx

### Optional runtime helpers
- python-dotenv if environment loading is desired
- or keep config environment-based only for the MVP

### Testing
- pytest
- pytest-asyncio if async endpoints or async LLM calls are used

### Tooling
- ruff for linting and formatting
- mypy or pyright if strict typing is desired later

### Dependency management
- uv

## Why these dependencies

### FastAPI
- Clean API layer
- Easy request/response validation with Pydantic
- Good fit for future web endpoints even if the MVP starts with CLI

### SQLite + SQLAlchemy
- Lightweight persistent state store
- Easy migration path to Postgres later if needed
- Good support for structured JSON payloads and versioned objects

### Pydantic
- Strong schema validation for:
  - city seeds
  - player requests
  - LLM outputs
  - runtime object contracts

### httpx
- Simple, provider-agnostic HTTP client for OpenAI-compatible LLM calls

### uv
- Fast dependency installation and execution
- Good fit for a small Python project

## Suggested pyproject dependency set

Runtime dependencies:
- fastapi
- uvicorn
- sqlalchemy
- pydantic
- httpx

Dev dependencies:
- pytest
- pytest-asyncio
- ruff

## Optional later additions
- alembic for migrations if schema changes become more complex
- orjson for faster JSON handling if profiling shows need
- pydantic-settings if configuration grows beyond environment variables

## MVP Recommendation

Start with the smallest workable set:
- fastapi
- uvicorn
- sqlalchemy
- pydantic
- httpx
- pytest
- ruff
- uv

Add more only when the MVP proves it needs them.
