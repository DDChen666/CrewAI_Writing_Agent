"""Command-line entry point for interacting with the Reddit scraping crew."""
from __future__ import annotations

import argparse
import json
import os
from typing import Any

os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

from crews.reddit_scraper import RedditScraperCrew


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interact with the Reddit scraping crew")
    parser.add_argument("prompt", help="Natural language instruction for the agent")
    return parser.parse_args()


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
    crew = RedditScraperCrew()
    result = crew.run(args.prompt)
    print(_serialize_result(result))


if __name__ == "__main__":
    main()
