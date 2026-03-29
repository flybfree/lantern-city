# Lantern City — Repo Bootstrap Commands

## Goal

Create a clean git repository and project scaffold for Lantern City before implementation begins.

## Assumed Root Directory

Use a project root such as:
- `~/lantern-city/`

Adjust as needed if you choose a different location.

## Bootstrap Commands

### 1. Create the project directory and initialize git

```bash
mkdir -p ~/lantern-city
cd ~/lantern-city
git init
```

### 2. Create the initial folder structure

```bash
mkdir -p src/lantern_city/generation tests docs backend
```

### 3. Add initial project files

At minimum, create:
- `README.md`
- `pyproject.toml`
- `.gitignore`

### 4. Add the ignore rules

Use the `.gitignore` draft from:
- `~/lantern-city-docs/backend/gitignore-draft.txt`

Recommended command if you want to copy it into the repo:

```bash
cp ~/lantern-city-docs/backend/gitignore-draft.txt ~/lantern-city/.gitignore
```

### 5. Copy the design docs into the repo docs folder if desired

If you want the working docs versioned in the repo:

```bash
cp -R ~/lantern-city-docs/* ~/lantern-city/docs/
```

If you prefer to keep docs outside the repo, skip this step and just reference the external workspace.

### 6. Create the first commit for documentation

```bash
git add README.md pyproject.toml .gitignore docs/
git commit -m "docs: add Lantern City design and backend specs"
```

### 7. Install dependencies and create the environment

With `uv`:

```bash
uv venv
source .venv/bin/activate
uv add fastapi uvicorn sqlalchemy pydantic httpx
uv add --dev pytest pytest-asyncio ruff
```

If you prefer to edit `pyproject.toml` first and then install:

```bash
uv sync
```

### 8. Verify tooling works

```bash
pytest --version
ruff --version
python --version
```

### 9. Commit the scaffold

```bash
git add src/ tests/ pyproject.toml
git commit -m "chore: scaffold Lantern City project structure"
```

## Recommended First Implementation Commits

1. `feat: add core world-state models`
2. `feat: add sqlite persistence layer`
3. `feat: add seed validation and bootstrap`
4. `feat: add request orchestration`
5. `feat: add llm interface and generation tasks`
6. `feat: add clues lanterns progression and cases`
7. `feat: add caching and background precompute`
8. `feat: add minimal playable shell`
9. `test: add end-to-end coverage`

## Optional Git Workflow

If you want a branch-based workflow:

```bash
git checkout -b feat/storage
```

Suggested branches:
- `feat/storage`
- `feat/seed-bootstrap`
- `feat/request-lifecycle`
- `feat/llm-interface`
- `feat/playable-shell`

## Design Rule

Keep the bootstrap simple and reproducible.
The first goal is not cleverness — it is a stable repo that can support disciplined implementation.
