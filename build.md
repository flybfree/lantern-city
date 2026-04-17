# Building Lantern City

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package and environment manager

uv will handle Python 3.12 and all dependencies automatically.

## Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd lantern-city

# 2. Install all dependencies including build tools
uv sync --dev

# 3. Build the executable
uv run pyinstaller lantern-city-tui.spec
```

The executable is written to:

```
dist/lantern-city-tui.exe        # Windows
dist/lantern-city-tui            # Linux / macOS
```

## Running the executable

The built executable is self-contained — no Python or uv required on the target machine.

```bash
# Launch the TUI (city picker appears at startup)
dist/lantern-city-tui.exe

# Open a specific city database directly
dist/lantern-city-tui.exe --db my-city.sqlite3
```

## Generating a city from the command line

Cities can also be generated without the TUI using the standalone script:

```bash
uv run python generate_city.py --url http://localhost:11434/v1 --model llama3 --concept "port city under military occupation"
```

See `generate_city.py --help` for all options.

## Notes

- `dist/` and `build/` are excluded from the repository — run the build locally on each machine.
- The `.spec` file (`lantern-city-tui.spec`) is committed and controls exactly what PyInstaller bundles.
- City database files (`*.sqlite3`) and LLM config files (`*.json`) are also excluded from the repository.
