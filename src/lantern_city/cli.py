from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from lantern_city.active_slice import MissingWorldObjectError
from lantern_city.app import LanternCityApp
from lantern_city.llm_client import OpenAICompatibleConfig
from lantern_city.prompt_diagnostics import run_prompt_diagnostics

DEFAULT_PROMPT_PROFILE = "default"
_GLOBAL_CONFIG_FILENAME = "lantern-city.profiles.json"


def _parse_startup_mode_arg(value: str) -> str:
    if value in {"auto", "mvp_baseline", "generated_runtime"}:
        return value
    raise argparse.ArgumentTypeError(
        "startup mode must be one of: generated_runtime, mvp_baseline"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lantern-city")
    parser.add_argument("--db", dest="database_path", default="lantern-city.sqlite3")
    parser.add_argument("--llm-url", dest="llm_url", default=None)
    parser.add_argument("--llm-model", dest="llm_model", default=None)
    parser.add_argument(
        "--startup-mode",
        dest="startup_mode",
        type=_parse_startup_mode_arg,
        metavar="{generated_runtime,mvp_baseline}",
        default="auto",
        help="player-facing startup style; internal 'auto' compatibility is still accepted",
    )
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

    prompt_check_parser = subparsers.add_parser("prompt-check")
    prompt_check_parser.add_argument("--concept", default="", help="optional city concept for diagnostics")
    prompt_check_parser.add_argument(
        "--report",
        default=None,
        help="optional path to save the prompt diagnostics JSON report",
    )
    return parser

def _shared_config_path() -> Path:
    return Path.cwd() / _GLOBAL_CONFIG_FILENAME


def _default_profile_name(url: str, model: str) -> str:
    cleaned_url = url.removeprefix("http://").removeprefix("https://").rstrip("/")
    host = cleaned_url.replace("/v1", "")
    return f"{host} | {model}"


def _load_llm_profiles(database_path: str) -> list[dict[str, str]]:
    path = _shared_config_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    raw_profiles = data.get("profiles")
    profiles: list[dict[str, str]] = []
    if isinstance(raw_profiles, list):
        for entry in raw_profiles:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("llm_url", "")).strip()
            model = str(entry.get("llm_model", "")).strip()
            if not url or not model:
                continue
            name = str(entry.get("name", "")).strip() or _default_profile_name(url, model)
            startup_mode = str(entry.get("startup_mode", "")).strip()
            if startup_mode not in {"auto", "mvp_baseline", "generated_runtime"}:
                startup_mode = "generated_runtime"
            prompt_profile = (
                str(entry.get("prompt_profile", "")).strip() or DEFAULT_PROMPT_PROFILE
            )
            profiles.append(
                {
                    "name": name,
                    "llm_url": url,
                    "llm_model": model,
                    "startup_mode": startup_mode,
                    "prompt_profile": prompt_profile,
                }
            )
    return profiles


def _load_active_llm_profile(database_path: str) -> dict[str, str] | None:
    profiles = _load_llm_profiles(database_path)
    if not profiles:
        return None
    path = _shared_config_path()
    active_name = ""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            active_name = str(data.get("active_profile", "")).strip()
        except (json.JSONDecodeError, OSError):
            active_name = ""
    if active_name:
        for profile in profiles:
            if profile["name"] == active_name:
                return profile
    return profiles[0]


def _load_llm_config(database_path: str) -> OpenAICompatibleConfig | None:
    profile = _load_active_llm_profile(database_path)
    if profile is None:
        return None
    return OpenAICompatibleConfig(
        base_url=profile["llm_url"],
        model=profile["llm_model"],
    )


def _load_startup_mode(database_path: str) -> str | None:
    profile = _load_active_llm_profile(database_path)
    if profile is None:
        return None
    startup_mode = profile["startup_mode"]
    return startup_mode if startup_mode in {"auto", "mvp_baseline", "generated_runtime"} else None


def _load_prompt_profile(database_path: str) -> str | None:
    profile = _load_active_llm_profile(database_path)
    if profile is None:
        return None
    return profile.get("prompt_profile") or DEFAULT_PROMPT_PROFILE


def _save_llm_config(
    database_path: str,
    url: str,
    model: str,
    *,
    startup_mode: str | None = None,
    profile_name: str | None = None,
    prompt_profile: str | None = None,
) -> None:
    path = _shared_config_path()
    profiles = _load_llm_profiles(database_path)
    active = _load_active_llm_profile(database_path)
    resolved_name = (profile_name or "").strip() or _default_profile_name(url, model)
    resolved_startup_mode = startup_mode
    if resolved_startup_mode is None:
        resolved_startup_mode = (
            active["startup_mode"]
            if active is not None
            else "generated_runtime"
        )
    resolved_prompt_profile = (
        (prompt_profile or "").strip()
        or (active["prompt_profile"] if active is not None else DEFAULT_PROMPT_PROFILE)
    )
    replacement = {
        "name": resolved_name,
        "llm_url": url,
        "llm_model": model,
        "startup_mode": resolved_startup_mode,
        "prompt_profile": resolved_prompt_profile,
    }
    updated_profiles: list[dict[str, str]] = []
    replaced = False
    for profile in profiles:
        if profile["name"] == resolved_name:
            updated_profiles.append(replacement)
            replaced = True
        else:
            updated_profiles.append(profile)
    if not replaced:
        updated_profiles.append(replacement)
    payload: dict[str, object] = {
        "active_profile": resolved_name,
        "profiles": updated_profiles,
        "llm_url": url,
        "llm_model": model,
        "startup_mode": resolved_startup_mode,
        "prompt_profile": resolved_prompt_profile,
    }
    path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _default_player_startup_mode(*, has_llm_config: bool) -> str:
    return "generated_runtime" if has_llm_config else "mvp_baseline"


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    from lantern_city.log import configure as _configure_logging
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.database_path)

    if args.llm_url and args.llm_model:
        startup_mode = args.startup_mode
        if startup_mode == "auto":
            startup_mode = _load_startup_mode(args.database_path) or _default_player_startup_mode(
                has_llm_config=True
            )
        _save_llm_config(
            args.database_path,
            args.llm_url,
            args.llm_model,
            startup_mode=startup_mode,
        )
        llm_config = OpenAICompatibleConfig(base_url=args.llm_url, model=args.llm_model)
    else:
        llm_config = _load_llm_config(args.database_path)
        startup_mode = args.startup_mode
        if startup_mode == "auto":
            startup_mode = _load_startup_mode(args.database_path) or _default_player_startup_mode(
                has_llm_config=llm_config is not None
            )

    app = LanternCityApp(
        Path(args.database_path),
        llm_config=llm_config,
        startup_mode=startup_mode,
    )

    try:
        if args.command == "prompt-check":
            if llm_config is None:
                output = "Error: prompt-check requires llm_config (--llm-url / --llm-model or saved config)."
            else:
                report = run_prompt_diagnostics(
                    llm_config=llm_config,
                    concept=getattr(args, "concept", ""),
                )
                output = report.to_text()
                report_path = getattr(args, "report", None)
                if report_path:
                    saved = report.write_json(report_path)
                    output = f"{output}\n\nReport saved: {saved}"
        elif args.command == "start":
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
    except ValueError as exc:
        output = f"Error: {exc}"

    destination = stdout or sys.stdout
    destination.write(f"{output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
