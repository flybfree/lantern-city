# Lantern City — Repo Setup Checklist

## Purpose

This checklist gets the Lantern City repository into a clean, implementation-ready state.

## Steps

### 1. Create the repository root

```bash
mkdir -p ~/lantern-city
cd ~/lantern-city
```

### 2. Initialize git

```bash
git init
```

### 3. Add the project skeleton

```bash
mkdir -p src/lantern_city/generation tests docs backend
mkdir -p src/lantern_city
```

### 4. Add the base files

Create:
- `README.md`
- `pyproject.toml`
- `.gitignore`

### 5. Use the refined pyproject content

Copy the finalized content from:
- `~/lantern-city-docs/backend/pyproject-toml-actual.md`

into the repo root as `pyproject.toml`.

### 6. Add the .gitignore rules

Copy or create `.gitignore` using the draft from:
- `~/lantern-city-docs/backend/gitignore-draft.txt`

### 7. Decide whether to version the docs inside the repo

Options:
- copy the docs workspace into `docs/`
- or keep docs externally and only reference them during implementation

If you want the docs committed:

```bash
cp -R ~/lantern-city-docs/* ~/lantern-city/docs/
```

### 8. Make the first docs commit

```bash
git add README.md pyproject.toml .gitignore docs/
git commit -m "docs: add Lantern City design and backend specs"
```

### 9. Create and activate the virtual environment

```bash
uv venv
source .venv/bin/activate
```

### 10. Install dependencies

```bash
uv add fastapi uvicorn sqlalchemy pydantic httpx
uv add --dev pytest pytest-asyncio ruff
```

If you prefer to rely on the committed `pyproject.toml` and lockfile:

```bash
uv sync
```

### 11. Verify tooling

```bash
pytest --version
ruff --version
python --version
```

### 12. Commit the scaffold

```bash
git add src/ tests/ pyproject.toml
 git commit -m "chore: scaffold Lantern City project structure"
```

## Suggested Ongoing Workflow

- Make one commit per task whenever possible.
- Keep tests passing before committing.
- Keep docs in sync with implementation changes.
- Use branches if you want feature isolation, but for solo work direct commits to main are acceptable.

## First Implementation Targets

After setup, begin with:
1. core models
2. serialization
3. SQLite storage
4. seed validation
5. city bootstrap

## Design Rule

If the repo cannot be bootstrapped quickly and repeatably, the implementation phase will become noisy.
Keep setup simple, explicit, and reproducible.
