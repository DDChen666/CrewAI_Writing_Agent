"""Command-line entry point for interacting with the Reddit scraping crew."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

from crews.reddit_scraper import RedditScraperCrew
from crews.reddit_scraper.tools import (
    get_tool_execution_log,
    reset_tool_execution_log,
)
from cli_common import (
    load_config,
    persist_result_if_json,
    resolve_prompt,
    serialize_result,
)


CONFIG_PATH = Path(__file__).with_name("scraper.json")
DEFAULT_PROMPTS = {
    "1": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "reddit_scraper",
        "task": "1",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interact with the Reddit scraping crew")
    parser.add_argument("prompt", help="Natural language instruction for the agent")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(CONFIG_PATH)
    output_root = Path(config.get("output_root", "scraepr_outputs"))
    crew = RedditScraperCrew()
    reset_tool_execution_log()
    template = resolve_prompt(args.prompt, DEFAULT_PROMPTS)
    prompt = template.prompt
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
        saved_path = persist_result_if_json(payload, output_root, stem=stem)
        if saved_path is not None:
            saved_paths.append(saved_path)

    print(serialize_result(result))
    if saved_paths:
        for path in saved_paths:
            print(f"Saved output to {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
