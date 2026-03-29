# Lantern City — Git Bootstrap Checklist

## Goal

Set up the repository cleanly so implementation can proceed in small, reviewable commits.

## Recommended Bootstrap Steps

### 1. Initialize the repository
- Create the project root directory if it does not already exist.
- Run `git init` in the root.
- Confirm the default branch name you want to use (usually `main`).

### 2. Add a `.gitignore`
Include common Python and tooling artifacts:
- `__pycache__/`
- `*.pyc`
- `.pytest_cache/`
- `.ruff_cache/`
- `.venv/`
- `dist/`
- `build/`
- `.mypy_cache/`
- `.DS_Store`
- SQLite database files if you do not want them committed
- local env files such as `.env`

### 3. Create the base project skeleton
Recommended initial files/folders:
- `pyproject.toml`
- `README.md`
- `src/lantern_city/`
- `tests/`
- `docs/`

### 4. Commit the documentation baseline
Before writing code, commit the design docs so the implementation can refer to a stable spec.

Suggested commit message:
- `docs: add Lantern City design and backend specs`

### 5. Create a development branch strategy
Use either:
- direct commits to `main` for solo development, or
- feature branches if you want a cleaner review flow

Suggested branch names:
- `feat/storage`
- `feat/seed-bootstrap`
- `feat/request-lifecycle`
- `feat/llm-interface`

### 6. Add dependency and tooling setup
Once the repo is initialized:
- add `pyproject.toml`
- install dependencies with `uv`
- verify `pytest` and `ruff` can run

### 7. Commit the initial scaffold
After the skeleton exists, commit it separately from the first backend feature.

Suggested commit message:
- `chore: scaffold Lantern City project structure`

### 8. Work in small commits mapped to the tasklist
Each task should ideally produce one commit or a small series of commits.

Suggested pattern:
- one task = one commit
- one commit = one logical change
- test before commit whenever possible

## Suggested Commit Sequence

1. `docs: add Lantern City design and backend specs`
2. `chore: initialize python project scaffold`
3. `feat: add core world-state models`
4. `feat: add sqlite persistence layer`
5. `feat: add seed validation and bootstrap`
6. `feat: add request orchestration`
7. `feat: add llm interface and generation tasks`
8. `feat: add clues lanterns progression and cases`
9. `feat: add caching and background precompute`
10. `feat: add minimal playable shell`
11. `test: add end-to-end coverage`

## Design Rule

Keep git history clean enough that you can answer:
- what changed?
- why did it change?
- does each commit still pass tests?

If yes, the repo is in good shape for implementation.
