# Lantern City — pyproject.toml Draft

Below is a recommended `pyproject.toml` draft for the Lantern City MVP.

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

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
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "pydantic>=2.7",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "ruff>=0.6",
]

[project.scripts]
lantern-city = "lantern_city.cli:main"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N"]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.12"
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
no_implicit_optional = true
strict_equality = true
ignore_missing_imports = true
```

## Notes

- This draft assumes a `src/` layout.
- `setuptools` is used for simplicity; `uv` can still manage the environment and dependencies.
- `lantern-city = "lantern_city.cli:main"` assumes the CLI entry point is implemented later.
- If you decide not to use mypy initially, you can remove the `[tool.mypy]` section.

## If you want a stricter minimalist version

You could trim this down to:
- project metadata
- runtime dependencies
- dev dependencies
- pytest config
- ruff config

and leave out `mypy` until later.
```