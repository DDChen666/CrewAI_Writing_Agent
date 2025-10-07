"""Command-line entry point for the Writing Agent crew."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from cli_common import load_config, persist_result_if_json, resolve_prompt, serialize_result
from crews.writing_agent import WritingAgentCrew


CONFIG_PATH = Path(__file__).with_name("writing_agent_config.json")
DEFAULT_PROMPTS = {
    "1": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "writing_agent",
        "task": "writing_agent_default",
    },
    "2": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "writing_agent",
        "task": "writing_agent_v2",
    },
    "3": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "writing_agent",
        "task": "writing_agent_v3",
    },
    "4": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "writing_agent",
        "task": "writing_agent_v4",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Writing Agent crew")
    parser.add_argument("prompt", help="Rewrite instructions for the Writing Agent")
    return parser.parse_args()


def _strip_code_fence(raw: str) -> str:
    stripped = raw.strip()
    if not stripped.startswith("```"):
        return stripped
    newline_index = stripped.find("\n")
    if newline_index == -1:
        return ""
    stripped = stripped[newline_index + 1 :]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    elif "\n```" in stripped:
        stripped = stripped.rsplit("\n```", 1)[0]
    return stripped.strip()


_JSON_FENCE_PATTERN = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def _extract_first_json_snippet(text: str) -> Optional[str]:
    start: Optional[int] = None
    stack: list[str] = []
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char in "{[":
            if start is None:
                start = index
            stack.append('}' if char == '{' else ']')
            continue

        if char in "}]" and stack:
            expected = stack.pop()
            if char != expected:
                stack.clear()
                start = None
                continue
            if not stack and start is not None:
                return text[start : index + 1]

    return None


def _parse_json_blob(blob: Optional[str]) -> Optional[Any]:
    if not blob or not isinstance(blob, str):
        return None

    candidate = _strip_code_fence(blob).strip()
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    for match in _JSON_FENCE_PATTERN.finditer(blob):
        snippet = match.group(1).strip()
        if not snippet:
            continue
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            continue

    snippet = _extract_first_json_snippet(blob)
    if snippet:
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None

    return None


def _find_latest_output(root: Path, pattern: str) -> Optional[Path]:
    candidates = list(root.rglob(pattern))
    latest_path: Optional[Path] = None
    latest_mtime: float = -1.0
    for path in candidates:
        if not path.is_file():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime > latest_mtime:
            latest_path = path
            latest_mtime = mtime
    return latest_path


def _load_pipeline_context(pipeline_file: Path) -> Tuple[Dict[str, Any], Dict[str, str]]:
    with pipeline_file.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    tasks_output = payload.get("tasks_output") or []
    raw_by_agent: Dict[str, str] = {}
    for task in tasks_output:
        agent_name = task.get("agent")
        raw_value = task.get("raw")
        if isinstance(agent_name, str) and isinstance(raw_value, str):
            raw_by_agent[agent_name] = raw_value

    brand_alignment = _parse_json_blob(raw_by_agent.get("Brand Alignment Agent"))
    topic_curator = _parse_json_blob(raw_by_agent.get("Topic Curator Agent"))
    data_triage = _parse_json_blob(raw_by_agent.get("Data Triage Agent"))

    dataset_id: Optional[str] = None
    if isinstance(topic_curator, dict):
        dataset_id = topic_curator.get("dataset_id") or dataset_id
    if not dataset_id and isinstance(brand_alignment, dict):
        dataset_id = brand_alignment.get("dataset_id")
    if not dataset_id and isinstance(data_triage, dict):
        dataset_id = data_triage.get("dataset_id")

    scored_payload: Optional[Dict[str, Any]] = None
    if isinstance(brand_alignment, dict):
        scored_payload = {
            "originating_report_id": brand_alignment.get("originating_report_id"),
            "opportunities": brand_alignment.get("opportunities", []),
        }

    topic_briefs: Optional[Any] = None
    if isinstance(topic_curator, dict):
        topic_briefs = topic_curator.get("prioritized_topic_briefs")

    context: Dict[str, Any] = {
        "source_file": str(pipeline_file.as_posix()),
        "dataset_id": dataset_id,
        "scored_and_filtered_opportunities": scored_payload,
        "prioritized_topic_briefs": topic_briefs,
        "token_usage": payload.get("token_usage"),
    }

    return context, raw_by_agent


def _resolve_pipeline_file(template_scalars: Dict[str, Any]) -> Path:
    base_dir = Path(__file__).resolve().parent

    pipeline_path_value = template_scalars.get("pipeline_output_path")
    if pipeline_path_value:
        pipeline_path = Path(pipeline_path_value)
        if not pipeline_path.is_absolute():
            pipeline_path = base_dir / pipeline_path
        if not pipeline_path.exists():
            raise FileNotFoundError(f"Pipeline output not found: {pipeline_path}")
        return pipeline_path

    root_value = template_scalars.get("pipeline_output_root", "content_pipeline_outputs")
    pattern_value = template_scalars.get(
        "pipeline_output_pattern",
        "*_content_opportunity_pipeline.json",
    )
    root_path = Path(root_value)
    if not root_path.is_absolute():
        root_path = base_dir / root_path
    if not root_path.exists():
        raise FileNotFoundError(f"Pipeline output root not found: {root_path}")

    pipeline_path = _find_latest_output(root_path, pattern_value)
    if pipeline_path is None:
        raise FileNotFoundError(
            f"No pipeline output found in {root_path} matching pattern '{pattern_value}'"
        )
    return pipeline_path


def main() -> None:
    args = parse_args()
    config = load_config(CONFIG_PATH)
    output_root = Path(config.get("output_root", "writing_agent_outputs"))

    template = resolve_prompt(args.prompt, DEFAULT_PROMPTS)
    prompt = template.prompt

    try:
        pipeline_file = _resolve_pipeline_file(template.scalars)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    try:
        pipeline_context, raw_by_agent = _load_pipeline_context(pipeline_file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load pipeline context: {exc}", file=sys.stderr)
        sys.exit(1)

    crew = WritingAgentCrew()
    result = crew.run(
        user_request=prompt,
        pipeline_context=pipeline_context,
        data_triage_raw=raw_by_agent.get("Data Triage Agent"),
        trend_analysis_raw=raw_by_agent.get("Trend Analysis Agent"),
        brand_alignment_raw=raw_by_agent.get("Brand Alignment Agent"),
        topic_curator_raw=raw_by_agent.get("Topic Curator Agent"),
        dataset_id=pipeline_context.get("dataset_id"),
    )

    saved_path = persist_result_if_json(result, output_root, stem="writing_agent")
    print(serialize_result(result))
    if saved_path is not None:
        print(f"Saved output to {saved_path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - runtime guard
        print(f"Failed to execute Writing Agent: {exc}", file=sys.stderr)
        sys.exit(1)
