# Lantern City — Project Structure

## Recommended Repository Layout

```text
lantern-city/
├── pyproject.toml
├── README.md
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
│   ├── test_models.py
│   ├── test_serialization.py
│   ├── test_store.py
│   ├── test_seed_schema.py
│   ├── test_city_seed_generation.py
│   ├── test_bootstrap.py
│   ├── test_orchestrator.py
│   ├── test_active_slice.py
│   ├── test_engine.py
│   ├── test_llm_client.py
│   ├── test_district_generation.py
│   ├── test_npc_response.py
│   ├── test_clues.py
│   ├── test_lanterns.py
│   ├── test_progression.py
│   ├── test_cases.py
│   ├── test_fallout.py
│   ├── test_cache.py
│   ├── test_background.py
│   ├── test_cli.py
│   └── test_end_to_end.py
└── docs/
    └── Lantern City docs workspace (this project)
```

## Structure Principles

- `src/lantern_city/` contains all application code.
- `generation/` holds all narrow LLM-backed generation functions.
- `tests/` mirrors the application shape.
- Keep the runtime package small and explicit.
- Keep planning and design docs outside the runtime package.

## Notes

- If you later add a web UI, keep it as a separate frontend or `src/lantern_city/web/` module.
- If the project grows, consider splitting `generation/` and `state/` into subpackages.
- For the MVP, this structure is enough without overengineering.
