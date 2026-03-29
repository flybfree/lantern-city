from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from lantern_city.app import LanternCityApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lantern-city")
    parser.add_argument("--db", dest="database_path", default="lantern-city.sqlite3")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("start")

    enter_parser = subparsers.add_parser("enter")
    enter_parser.add_argument("district_id")

    talk_parser = subparsers.add_parser("talk")
    talk_parser.add_argument("npc_id")
    talk_parser.add_argument("prompt")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("location_id")

    case_parser = subparsers.add_parser("case")
    case_parser.add_argument("case_id")
    return parser


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = LanternCityApp(Path(args.database_path))

    if args.command == "start":
        output = app.start_new_game()
    elif args.command == "enter":
        output = app.enter_district(args.district_id)
    elif args.command == "talk":
        output = app.talk_to_npc(args.npc_id, args.prompt)
    elif args.command == "inspect":
        output = app.inspect_location(args.location_id)
    elif args.command == "case":
        output = app.advance_case(args.case_id)
    else:
        parser.error(f"Unsupported command: {args.command}")

    destination = stdout or sys.stdout
    destination.write(f"{output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
