from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from lantern_city.active_slice import MissingWorldObjectError
from lantern_city.app import LanternCityApp
from lantern_city.llm_client import OpenAICompatibleConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lantern-city")
    parser.add_argument("--db", dest="database_path", default="lantern-city.sqlite3")
    parser.add_argument("--llm-url", dest="llm_url", default=None)
    parser.add_argument("--llm-model", dest="llm_model", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("start")
    subparsers.add_parser("overview")
    subparsers.add_parser("clues")

    go_parser = subparsers.add_parser("go")
    go_parser.add_argument("location_id")

    look_parser = subparsers.add_parser("look")
    look_parser.add_argument("district_id", nargs="?", default=None)

    enter_parser = subparsers.add_parser("enter")
    enter_parser.add_argument("district_id")

    talk_parser = subparsers.add_parser("talk")
    talk_parser.add_argument("npc_id")
    talk_parser.add_argument("prompt")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("location_id")
    inspect_parser.add_argument("object_name", nargs="?", default=None)

    case_parser = subparsers.add_parser("case")
    case_parser.add_argument("case_id")
    return parser


def _config_path(database_path: str) -> Path:
    return Path(database_path).with_suffix(".json")


def _load_llm_config(database_path: str) -> OpenAICompatibleConfig | None:
    path = _config_path(database_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        url = data.get("llm_url")
        model = data.get("llm_model")
        if url and model:
            return OpenAICompatibleConfig(base_url=url, model=model)
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_llm_config(database_path: str, url: str, model: str) -> None:
    path = _config_path(database_path)
    path.write_text(
        json.dumps({"llm_url": url, "llm_model": model}, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.llm_url and args.llm_model:
        _save_llm_config(args.database_path, args.llm_url, args.llm_model)
        llm_config = OpenAICompatibleConfig(base_url=args.llm_url, model=args.llm_model)
    else:
        llm_config = _load_llm_config(args.database_path)

    app = LanternCityApp(Path(args.database_path), llm_config=llm_config)

    try:
        if args.command == "start":
            output = app.start_new_game()
        elif args.command == "overview":
            output = app.overview()
        elif args.command == "clues":
            output = app.clues()
        elif args.command == "go":
            output = app.go(args.location_id)
        elif args.command == "look":
            output = app.look(args.district_id)
        elif args.command == "enter":
            output = app.enter_district(args.district_id)
        elif args.command == "talk":
            output = app.talk_to_npc(args.npc_id, args.prompt)
        elif args.command == "inspect":
            output = app.inspect_location(args.location_id, getattr(args, "object_name", None))
        elif args.command == "case":
            output = app.advance_case(args.case_id)
        else:
            parser.error(f"Unsupported command: {args.command}")
    except MissingWorldObjectError as exc:
        output = (
            f"Error: {exc}\n"
            "Hint: run `enter <district_id>` first and use one of the IDs shown in the district output."
        )
    except LookupError as exc:
        output = f"Error: {exc}"

    destination = stdout or sys.stdout
    destination.write(f"{output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
