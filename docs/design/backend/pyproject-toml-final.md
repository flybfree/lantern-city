# Lantern City — Refined pyproject.toml

Below is a cleaner, more implementation-ready `pyproject.toml` for the Lantern City MVP.

```toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "lantern-city"
version = "0.1.0"
description = "Lantern City: a replayable text-first investigative RPG with persistent city state and lazy LLM generation"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [
  { name = "Hermes" }
]
keywords = ["rpg", "narrative", "llm", "world-simulation", "investigation", "text-game"]
classifiers = [
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.12",
  "License :: OSI Approved :: MIT License",
  "Intended Audience :: Developers",
  "Topic :: Games/Entertainment",
]
dependencies = [
  "fastapi>=0.115,<1.0",
  "uvicorn[standard]>=0.30,<1.0",
  "sqlalchemy>=2.0,<3.0",
  "pydantic>=2.7,<3.0",
  "httpx>=0.27,<1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0,<9.0",
  "pytest-asyncio>=0.23,<1.0",
  "ruff>=0.6,<1.0",
]

[project.scripts]
lantern-city = "lantern_city.cli:main"

[project.urls]
Homepage = "https://example.com/lantern-city"
Repository = "https://example.com/lantern-city.git"

[tool.hatch.build]
packages = ["src/lantern_city"]

[tool.hatch.build.targets.wheel]
packages = ["src/lantern_city"]

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N"]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.uv]
# Keep this minimal for now; uv will manage the environment and lockfile.
```

## Why this version is better

### 1. Hatchling build backend
- Simple and modern.
- Works cleanly with a `src/` layout.
- Keeps packaging lightweight for the MVP.

### 2. Version pins with upper bounds
- Lower bounds ensure required features exist.
- Upper bounds reduce surprise breakage during early development.
- Good for a small MVP while the stack is stabilizing.

### 3. Cleaner dev tooling
- `pytest` and `ruff` are enough for the MVP.
- `pytest-asyncio` is included because the backend may use async I/O.

### 4. CLI entry point placeholder
- `lantern-city = "lantern_city.cli:main"`
- This is enough to support a minimal playable shell later.

## Notes

- The `project.urls` values are placeholders and should be replaced when the repo is real.
- If you prefer `setuptools` instead of `hatchling`, that is also fine, but hatchling is cleaner for a new project.
- You can add `mypy` later if strict type checking becomes useful.
- You can add `alembic` later if the storage schema becomes migration-heavy.

## Minimal alternative

If you want the absolute smallest viable `pyproject.toml`, you can remove:
- `keywords`
- `classifiers`
- `project.urls`
- `tool.uv`
- optional type-checking config

But the version above is still simple and more complete.
