"""Command-line entry point for interacting with the Reddit scraping crew."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

from crews.reddit_scraper import RedditScraperCrew


CONFIG_PATH = Path(__file__).with_name("scraper.json")


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
    now = dt.datetime.now(dt.UTC)
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


def _persist_result_if_json(result: Any, output_root: Path) -> Optional[Path]:
    payload = _coerce_json_payload(result)
    if payload is None:
        return None
    if isinstance(payload, dict) and payload.get("status") == "error":
        return None
    try:
        path = _ensure_output_path(output_root, "reddit_agent")
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


def main() -> None:
    args = parse_args()
    config = _load_config()
    output_root = Path(config.get("output_root", "scraepr"))
    crew = RedditScraperCrew()
    result = crew.run(args.prompt)
    saved_path = _persist_result_if_json(result, output_root)
    print(_serialize_result(result))
    if saved_path is not None:
        print(f"Saved output to {saved_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
