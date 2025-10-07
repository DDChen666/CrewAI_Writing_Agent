"""Command-line entry point for the Content Opportunity Pipeline."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from cli_common import (
    load_config,
    persist_result_if_json,
    resolve_prompt,
    serialize_result,
)
from crews.content_opportunity_pipeline import ContentOpportunityPipelineCrew


CONFIG_PATH = Path(__file__).with_name("content_pipeline_config.json")
DEFAULT_PROMPTS = {
    "1": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "content_opportunity_pipeline",
        "task": "content_pipeline_default",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Content Opportunity Pipeline crew")
    parser.add_argument("prompt", help="Natural language instruction for the pipeline")
    parser.add_argument(
        "--brand-knowledge-base",
        dest="brand_knowledge_base",
        help="Path to the brand knowledge base file to provide as context",
    )
    return parser.parse_args()


def _load_brand_knowledge_base(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem guard
        raise RuntimeError(f"Unable to read brand knowledge base: {path}") from exc


def _determine_brand_kb_path(
    cli_value: Optional[str],
    config: dict,
    template_scalars: dict,
) -> Optional[Path]:
    if cli_value:
        return Path(cli_value)
    config_path = config.get("brand_knowledge_base")
    if isinstance(config_path, str) and config_path.strip():
        return Path(config_path)
    scalar_path = template_scalars.get("brand_knowledge_base")
    if scalar_path:
        return Path(scalar_path)
    return None


def main() -> None:
    args = parse_args()
    config = load_config(CONFIG_PATH)
    output_root = Path(config.get("output_root", "content_pipeline_outputs"))

    template = resolve_prompt(args.prompt, DEFAULT_PROMPTS)
    prompt = template.prompt

    kb_path = _determine_brand_kb_path(args.brand_knowledge_base, config, template.scalars)
    brand_knowledge_base: Optional[str] = None
    if kb_path is not None:
        base_dir = Path(__file__).resolve().parent
        resolved_path = kb_path if kb_path.is_absolute() else base_dir / kb_path
        if not resolved_path.exists():
            print(f"Brand knowledge base not found: {resolved_path}", file=sys.stderr)
            sys.exit(1)
        brand_knowledge_base = _load_brand_knowledge_base(resolved_path)

    if not os.environ.get("GEMINI_API_KEY"):
        print(
            "GEMINI_API_KEY environment variable is required to run the Content Opportunity Pipeline.",
            file=sys.stderr,
        )
        sys.exit(1)

    crew = ContentOpportunityPipelineCrew()
    result = crew.run(user_request=prompt, brand_knowledge_base=brand_knowledge_base)

    saved_path = persist_result_if_json(result, output_root, stem="content_opportunity_pipeline")
    print(serialize_result(result))
    if saved_path is not None:
        print(f"Saved output to {saved_path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - runtime guard
        print(f"Failed to execute Content Opportunity Pipeline: {exc}", file=sys.stderr)
        sys.exit(1)
