"""Command-line entry point for interacting with the Reddit scraping crew."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

from crews.reddit_scraper import RedditScraperCrew
from crews.reddit_scraper.tools import (
    get_tool_execution_log,
    reset_tool_execution_log,
)


CONFIG_PATH = Path(__file__).with_name("scraper.json")
DEFAULT_PROMPTS = {
    "1": Path(__file__).with_name("Default_Tasks1.YML"),
}
PROMPT_KEY = "prompt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interact with the Reddit scraping crew")
    parser.add_argument("prompt", help="Natural language instruction for the agent")
    return parser.parse_args()


def _load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _ensure_output_path(root: Path, stem: str) -> Path:
    try:
        tz = ZoneInfo("Asia/Taipei")
    except Exception:
        tz = dt.timezone(dt.timedelta(hours=8))
    now = dt.datetime.now(tz)
    directory = root / now.strftime("%Y%m%d")
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{now.strftime('%Y%m%d%H%M')}_{stem}.json"
    return directory / filename


def _write_output(path: Path, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def _coerce_json_payload(result: Any) -> Optional[Any]:
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return None
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, (dict, list)):
        return result
    return None


def _persist_result_if_json(result: Any, output_root: Path, stem: str = "reddit_agent") -> Optional[Path]:
    payload = _coerce_json_payload(result)
    if payload is None:
        return None
    if isinstance(payload, dict) and payload.get("status") == "error":
        return None
    try:
        path = _ensure_output_path(output_root, stem)
        _write_output(path, payload)
    except OSError:
        return None
    return path


def _serialize_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
    try:
        return json.dumps(result, ensure_ascii=False, indent=2)
    except TypeError:
        return str(result)


def _load_prompt_from_file(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to read prompt file: {path}") from exc

    lines = content.splitlines()
    prompt_lines = []
    capture = False
    indent = None

    for line in lines:
        stripped = line.strip()
        if not capture:
            if stripped.startswith(f"{PROMPT_KEY}:"):
                suffix = stripped[len(PROMPT_KEY) + 1 :].strip()
                if suffix and not suffix.startswith("|") and not suffix.startswith(">"):
                    return suffix
                capture = True
                continue
            continue

        if indent is None:
            if not line:
                prompt_lines.append("")
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent == 0:
                break

        if indent is not None and line.startswith(" " * indent):
            prompt_lines.append(line[indent:])
        elif not line and indent is not None:
            prompt_lines.append("")
        else:
            break

    if not prompt_lines:
        raise RuntimeError(f"Prompt not found in {path}")

    return "\n".join(prompt_lines).rstrip("\n")


def _resolve_prompt(prompt_arg: str) -> str:
    prompt_path = DEFAULT_PROMPTS.get(prompt_arg)
    if prompt_path is None:
        return prompt_arg
    if not prompt_path.exists():
        raise FileNotFoundError(f"Default prompt file not found: {prompt_path}")
    return _load_prompt_from_file(prompt_path)


def main() -> None:
    args = parse_args()
    config = _load_config()
    output_root = Path(config.get("output_root", "scraepr"))
    crew = RedditScraperCrew()
    reset_tool_execution_log()
    prompt = _resolve_prompt(args.prompt)
    result = crew.run(prompt)
    tool_outputs = get_tool_execution_log()

    errors = [entry for entry in tool_outputs if isinstance(entry["payload"], dict) and entry["payload"].get("status") == "error"]
    if errors:
        first_error = errors[0]
        message = first_error["payload"].get("message", "Unknown error")
        print(f"Tool '{first_error['tool']}' failed: {message}", file=sys.stderr)
        sys.exit(1)

    saved_paths = []
    for idx, entry in enumerate(tool_outputs, start=1):
        payload = entry["payload"]
        stem = f"reddit_agent_{idx}_{entry['tool']}"
        saved_path = _persist_result_if_json(payload, output_root, stem=stem)
        if saved_path is not None:
            saved_paths.append(saved_path)

    print(_serialize_result(result))
    if saved_paths:
        for path in saved_paths:
            print(f"Saved output to {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
