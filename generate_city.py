"""Standalone city generation script for Lantern City.

Generates a new city via LLM and saves it to a SQLite database file.
The resulting file can be opened with the game TUI.

Usage:
    uv run python generate_city.py --url http://localhost:11434/v1 --model llama3 \\
        [--concept TEXT] [--output cities/mytown.sqlite3]

    # Uses previously saved LLM config (set once via the TUI Ctrl+S):
    uv run python generate_city.py --concept "coastal city run by merchant guilds"

    # With no concept the LLM invents the city freely:
    uv run python generate_city.py --output worlds/new_city.sqlite3
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="generate-city",
        description="Generate a new Lantern City and save it to a database file.",
    )
    parser.add_argument(
        "--concept",
        default="",
        metavar="TEXT",
        help="Optional thematic concept for the city (e.g. 'port city under military occupation')",
    )
    parser.add_argument(
        "--output",
        default="lantern-city.sqlite3",
        metavar="FILE",
        help="Output SQLite database path (default: lantern-city.sqlite3)",
    )
    parser.add_argument(
        "--url",
        default=None,
        metavar="URL",
        help="LLM base URL, e.g. http://localhost:11434/v1",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="NAME",
        help="LLM model name, e.g. llama3 or mistral",
    )
    args = parser.parse_args()

    # Import after sys.path is set
    from lantern_city.app import LanternCityApp
    from lantern_city.cli import _load_llm_config, _save_llm_config
    from lantern_city.llm_client import OpenAICompatibleConfig

    out_name = args.output
    if not out_name.endswith(".sqlite3"):
        out_name = out_name.rstrip(".") + ".sqlite3"
    output = Path(out_name)
    if output.exists():
        print(f"ERROR: {output} already exists.")
        print("  Delete it first, or specify a different --output path.")
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)

    # Resolve LLM config
    if args.url and args.model:
        llm_config = OpenAICompatibleConfig(base_url=args.url, model=args.model)
        _save_llm_config(str(output), args.url, args.model)
    else:
        llm_config = _load_llm_config(str(output))
        if llm_config is None:
            # Try the default DB's saved config as fallback
            llm_config = _load_llm_config("lantern-city.sqlite3")
        if llm_config is None:
            print("ERROR: No LLM configured.")
            print("  Provide --url and --model, or configure once via the TUI (Ctrl+S).")
            return 1

    log_path = output.with_suffix(".generation.log")
    log_file = open(log_path, "w", encoding="utf-8")  # noqa: SIM115

    def _emit(msg: str) -> None:
        print(f"  {msg}", flush=True)
        log_file.write(msg + "\n")
        log_file.flush()

    header = (
        f"Output:  {output}\n"
        f"LLM:     {llm_config.base_url}  model: {llm_config.model}\n"
        + (f"Concept: {args.concept}\n" if args.concept else "")
    )
    print(header)
    log_file.write(header + "\n")

    game = LanternCityApp(output, llm_config=llm_config)
    try:
        result = game.start_new_game(
            concept=args.concept or None,
            on_progress=_emit,
        )
    except Exception as exc:
        msg = f"\nERROR during generation: {exc}"
        print(msg)
        log_file.write(msg + "\n")
        log_file.close()
        try:
            output.unlink()
        except OSError:
            pass
        return 1

    footer = f"\n{result}\n\nCity saved to: {output}\nLog: {log_path}"
    print(footer)
    log_file.write(footer + "\n")
    log_file.close()
    print(f"Open it with:  lantern-city-tui --db {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
