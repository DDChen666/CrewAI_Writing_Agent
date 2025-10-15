"""Command-line entry point for the Writing Agent crew."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from cli_common import (
    coerce_json_payload,
    DirectiveBlock,
    load_config,
    parse_prompt_directives,
    persist_result_if_json,
    resolve_prompt,
    serialize_result,
)
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
    parser.add_argument(
        "--skip-raw-export",
        dest="export_raw_articles",
        action="store_false",
        help="Skip exporting platform articles from the raw JSON payload to text files",
    )
    parser.set_defaults(export_raw_articles=True)
    return parser.parse_args()


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _get_value_from_candidates(
    data: Optional[Dict[str, Any]], candidates: Sequence[str]
) -> Optional[Any]:
    if not isinstance(data, dict) or not candidates:
        return None

    lowered_to_actual: Dict[str, str] = {
        k.lower(): k for k in data.keys() if isinstance(k, str)
    }
    normalized_to_actual: Dict[str, str] = {
        re.sub(r"[\s_\-]", "", k.lower()): k for k in data.keys() if isinstance(k, str)
    }

    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        value = data.get(candidate)
        if value is None:
            lowered_candidate = candidate.lower()
            actual_key = lowered_to_actual.get(lowered_candidate)
            if not actual_key:
                normalized_candidate = re.sub(r"[\s_\-]", "", lowered_candidate)
                actual_key = normalized_to_actual.get(normalized_candidate)
            if actual_key:
                value = data.get(actual_key)
        if _is_non_empty(value):
            return value
    return None


def _find_agent_raw(
    raw_map: Dict[str, Any], keywords: Sequence[str], *, match_any: bool = False
) -> Optional[str]:
    if not raw_map or not keywords:
        return None

    for agent_name, raw_value in raw_map.items():
        if not isinstance(agent_name, str) or not isinstance(raw_value, str):
            continue
        lowered_name = agent_name.lower()
        keyword_matches = [
            keyword.lower() in lowered_name for keyword in keywords if isinstance(keyword, str)
        ]
        if match_any and any(keyword_matches):
            return raw_value
        if not match_any and keyword_matches and all(keyword_matches):
            return raw_value
    return None


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


def _sanitize_filename_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_\-]+", "_", value.strip())
    sanitized = sanitized.strip("_")
    return sanitized or "article"


def _format_value_lines(value: Any, indent: int = 0) -> List[str]:
    indent_str = "    " * indent
    if isinstance(value, str):
        if not value:
            return [indent_str] if indent else [""]
        lines: List[str] = []
        for raw_line in value.splitlines():
            prefix = indent_str if indent else ""
            lines.append(f"{prefix}{raw_line}")
        if value.endswith("\n"):
            lines.append(indent_str if indent else "")
        return lines or ([indent_str] if indent else [""])
    if value is None:
        return [f"{indent_str}null"]
    if isinstance(value, bool):
        return [f"{indent_str}{str(value).lower()}"]
    if isinstance(value, (int, float)):
        return [f"{indent_str}{value}"]
    if isinstance(value, list):
        lines: List[str] = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{indent_str}-")
                lines.extend(_format_value_lines(item, indent + 1))
            else:
                item_str = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
                if isinstance(item, str) and "\n" in item:
                    split_lines = item.splitlines()
                    lines.append(f"{indent_str}- {split_lines[0]}")
                    for continuation in split_lines[1:]:
                        lines.append(f"{indent_str}  {continuation}")
                else:
                    lines.append(f"{indent_str}- {item_str}")
        return lines
    if isinstance(value, dict):
        lines: List[str] = []
        for key, nested in value.items():
            lines.append(f"{indent_str}{key}:")
            lines.extend(_format_value_lines(nested, indent + 1))
        return lines
    return [f"{indent_str}{json.dumps(value, ensure_ascii=False)}"]


def _article_payload_to_text(article: Any) -> str:
    if isinstance(article, str):
        return article.strip() + ("\n" if not article.endswith("\n") else "")
    if isinstance(article, dict):
        lines: List[str] = []
        for key, value in article.items():
            lines.append(f"{key}:")
            lines.extend(_format_value_lines(value, indent=1))
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
        return ("\n".join(lines)).rstrip() + "\n"
    if isinstance(article, list):
        lines = _format_value_lines(article, indent=0)
        return ("\n".join(lines)).rstrip() + "\n"
    return json.dumps(article, ensure_ascii=False, indent=2) + "\n"


def _export_articles_from_raw(raw_value: Any, output_path: Path) -> List[Path]:
    if not isinstance(raw_value, str):
        return []

    parsed = _parse_json_blob(raw_value)
    if not isinstance(parsed, dict):
        return []

    target_dir = output_path.with_suffix("")
    articles_written: List[Path] = []

    for section_name, entries in parsed.items():
        if not isinstance(entries, list):
            continue
        safe_section = _sanitize_filename_component(section_name)
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, (dict, list, str)):
                continue
            article_text = _article_payload_to_text(entry)
            if not article_text.strip():
                continue
            filename = f"{safe_section}_{index:02d}.txt"
            article_path = target_dir / filename
            article_path.parent.mkdir(parents=True, exist_ok=True)
            article_path.write_text(article_text, encoding="utf-8")
            articles_written.append(article_path)
    return articles_written


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


_DATASET_ID_KEYS = ["dataset_id", "report_id", "originating_report_id", "id"]
_DATASET_CONTAINER_KEYS = [
    "identified_trends_report",
    "identified_trends",
    "report_metadata",
    "dataset",
    "report",
]
_SCORED_KEYS = [
    "scored_and_filtered_opportunities",
    "scored_opportunities",
    "scored_opps",
    "filtered_opportunities",
]
_TOPIC_BRIEF_KEYS = [
    "prioritized_topic_briefs",
    "prioritized_topic_brief",
    "topic_briefs",
    "topic_brief",
]
_TOPIC_BRIEF_LIST_KEYS = [
    "briefs",
    "prioritized_topic_briefs",
    "prioritized_briefs",
    "brief_list",
    "prioritized_topics",
    "topics",
]


def _normalize_topic_briefs(value: Any) -> Optional[list[Any]]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        nested_list = _get_value_from_candidates(value, _TOPIC_BRIEF_LIST_KEYS)
        if isinstance(nested_list, list):
            return list(nested_list)
        if {"topic_id", "title"} <= {k for k in value.keys() if isinstance(k, str)}:
            return [value]
    return None


def _load_pipeline_context(pipeline_file: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    with pipeline_file.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    tasks_output = payload.get("tasks_output") or []
    raw_by_agent: Dict[str, str] = {}
    for task in tasks_output:
        agent_name = task.get("agent")
        raw_value = task.get("raw")
        if isinstance(agent_name, str) and isinstance(raw_value, str):
            raw_by_agent[agent_name] = raw_value

    brand_alignment_raw = _find_agent_raw(raw_by_agent, ["brand", "alignment"])
    topic_curator_raw = _find_agent_raw(
        raw_by_agent, ["topic", "curator"], match_any=True
    )
    data_triage_raw = _find_agent_raw(raw_by_agent, ["data", "triage"])
    trend_analysis_raw = _find_agent_raw(raw_by_agent, ["trend", "analysis"])

    brand_alignment = _parse_json_blob(brand_alignment_raw)
    topic_curator = _parse_json_blob(topic_curator_raw)
    data_triage = _parse_json_blob(data_triage_raw)

    dataset_id = _get_value_from_candidates(payload, _DATASET_ID_KEYS)
    if not dataset_id:
        for container_key in _DATASET_CONTAINER_KEYS:
            dataset_id = _get_value_from_candidates(
                payload.get(container_key), _DATASET_ID_KEYS
            )
            if dataset_id:
                break
    if not dataset_id and isinstance(topic_curator, dict):
        dataset_id = _get_value_from_candidates(topic_curator, _DATASET_ID_KEYS)
    if not dataset_id and isinstance(brand_alignment, dict):
        dataset_id = _get_value_from_candidates(brand_alignment, _DATASET_ID_KEYS)
    if not dataset_id and isinstance(data_triage, dict):
        dataset_id = _get_value_from_candidates(data_triage, _DATASET_ID_KEYS)

    if isinstance(dataset_id, dict):
        nested_dataset = _get_value_from_candidates(dataset_id, _DATASET_ID_KEYS)
        if nested_dataset:
            dataset_id = nested_dataset
    if isinstance(dataset_id, (list, tuple, set)):
        dataset_id = next(
            (
                item.strip()
                for item in dataset_id
                if isinstance(item, str) and item.strip()
            ),
            None,
        )
    if isinstance(dataset_id, str):
        dataset_id = dataset_id.strip() or None
    elif dataset_id is not None and not isinstance(dataset_id, str):
        dataset_id = str(dataset_id)

    scored_payload: Optional[Any] = _get_value_from_candidates(payload, _SCORED_KEYS)
    if not scored_payload:
        for container_key in _DATASET_CONTAINER_KEYS + ["topic_curator", "analysis"]:
            scored_payload = _get_value_from_candidates(
                payload.get(container_key), _SCORED_KEYS
            )
            if scored_payload:
                break
    if not scored_payload and isinstance(brand_alignment, dict):
        scored_payload = _get_value_from_candidates(brand_alignment, _SCORED_KEYS)
        if not scored_payload:
            opportunities_from_brand = _get_value_from_candidates(
                brand_alignment, ["opportunities", "scored_opportunities"]
            )
            if isinstance(opportunities_from_brand, list):
                scored_payload = {
                    "originating_report_id": _get_value_from_candidates(
                        brand_alignment, _DATASET_ID_KEYS
                    ),
                    "opportunities": opportunities_from_brand,
                }
    if not scored_payload and isinstance(data_triage, dict):
        scored_payload = _get_value_from_candidates(data_triage, _SCORED_KEYS)

    if isinstance(scored_payload, dict):
        scored_payload = dict(scored_payload)
    elif isinstance(scored_payload, list):
        scored_payload = {"opportunities": list(scored_payload)}
    else:
        scored_payload = None

    if scored_payload is None:
        scored_payload = {"opportunities": []}
    else:
        if "opportunities" not in scored_payload:
            fallback_opportunities = _get_value_from_candidates(
                scored_payload,
                ["scored_opportunities", "filtered_opportunities", "opportunities"],
            )
            if isinstance(fallback_opportunities, list):
                scored_payload["opportunities"] = list(fallback_opportunities)
            elif _is_non_empty(fallback_opportunities):
                scored_payload["opportunities"] = [fallback_opportunities]
            else:
                scored_payload["opportunities"] = []
        opportunities_value = scored_payload.get("opportunities")
        if isinstance(opportunities_value, list):
            scored_payload["opportunities"] = list(opportunities_value)
        elif isinstance(opportunities_value, (tuple, set)):
            scored_payload["opportunities"] = list(opportunities_value)
        elif _is_non_empty(opportunities_value):
            scored_payload["opportunities"] = [opportunities_value]
        else:
            scored_payload["opportunities"] = []
        if not _is_non_empty(scored_payload.get("originating_report_id")) and dataset_id:
            scored_payload["originating_report_id"] = dataset_id

    topic_briefs_notes: Optional[Any] = None
    topic_briefs_source = _get_value_from_candidates(payload, _TOPIC_BRIEF_KEYS)
    if isinstance(topic_briefs_source, dict):
        topic_briefs_notes = _get_value_from_candidates(
            topic_briefs_source,
            [
                "selected_opportunities_rationale",
                "selection_rationale",
                "summary",
            ],
        )
    topic_briefs = _normalize_topic_briefs(topic_briefs_source) or []
    if not topic_briefs and isinstance(topic_curator, dict):
        curated_value = _get_value_from_candidates(topic_curator, _TOPIC_BRIEF_KEYS)
        topic_briefs = (
            _normalize_topic_briefs(curated_value)
            or _normalize_topic_briefs(topic_curator)
            or topic_briefs
        )
        if topic_briefs_notes is None and isinstance(topic_curator, dict):
            topic_briefs_notes = _get_value_from_candidates(
                topic_curator,
                [
                    "selected_opportunities_rationale",
                    "selection_rationale",
                    "summary",
                ],
            )
    if not topic_briefs and isinstance(brand_alignment, dict):
        brand_value = _get_value_from_candidates(brand_alignment, _TOPIC_BRIEF_KEYS)
        topic_briefs = _normalize_topic_briefs(brand_value) or topic_briefs
    if not topic_briefs:
        topic_briefs = []

    if topic_briefs_notes is not None and not isinstance(topic_briefs_notes, str):
        try:
            topic_briefs_notes = json.dumps(topic_briefs_notes, ensure_ascii=False)
        except (TypeError, ValueError):
            topic_briefs_notes = str(topic_briefs_notes)

    context: Dict[str, Any] = {
        "source_file": str(pipeline_file.as_posix()),
        "dataset_id": dataset_id,
        "scored_and_filtered_opportunities": scored_payload,
        "prioritized_topic_briefs": topic_briefs,
        "prioritized_topic_briefs_notes": topic_briefs_notes,
        "token_usage": payload.get("token_usage"),
    }

    agent_payloads: Dict[str, Any] = {
        "raw_by_agent": raw_by_agent,
        "brand_alignment_raw": brand_alignment_raw,
        "topic_curator_raw": topic_curator_raw,
        "data_triage_raw": data_triage_raw,
        "trend_analysis_raw": trend_analysis_raw,
    }

    return context, agent_payloads


def _resolve_pipeline_file(
    template_scalars: Dict[str, Any],
    directive_block: Optional[DirectiveBlock],
) -> Path:
    base_dir = Path(__file__).resolve().parent

    pipeline_path_value = template_scalars.get("pipeline_output_path")
    if directive_block:
        override_path = (
            directive_block.parameters.get("pipeline_output_path")
            or directive_block.parameters.get("pipeline_file")
            or directive_block.parameters.get("pipeline_path")
        )
        if isinstance(override_path, str) and override_path.strip():
            pipeline_path_value = override_path.strip()

    if pipeline_path_value:
        pipeline_path = Path(pipeline_path_value)
        if not pipeline_path.is_absolute():
            pipeline_path = base_dir / pipeline_path
        if not pipeline_path.exists():
            raise FileNotFoundError(f"Pipeline output not found: {pipeline_path}")
        return pipeline_path

    root_value = template_scalars.get("pipeline_output_root", "content_pipeline_outputs")
    if directive_block:
        override_root = directive_block.parameters.get("pipeline_output_root") or directive_block.parameters.get("pipeline_root")
        if isinstance(override_root, str) and override_root.strip():
            root_value = override_root.strip()
    pattern_value = template_scalars.get(
        "pipeline_output_pattern",
        "*_content_opportunity_pipeline.json",
    )
    if directive_block:
        override_pattern = directive_block.parameters.get("pipeline_output_pattern") or directive_block.parameters.get("pipeline_pattern")
        if isinstance(override_pattern, str) and override_pattern.strip():
            pattern_value = override_pattern.strip()
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
    prompt_meta = parse_prompt_directives(template.prompt)

    def _block_copy(block: Optional[DirectiveBlock]) -> DirectiveBlock:
        if block is None:
            return DirectiveBlock(instructions="", parameters={})
        return DirectiveBlock(
            instructions=block.instructions,
            parameters=dict(block.parameters),
        )

    def _directive(*names: str) -> DirectiveBlock:
        for name in names:
            block = prompt_meta.blocks.get(name)
            if block and (block.instructions.strip() or block.parameters):
                return _block_copy(block)
        return DirectiveBlock(instructions="", parameters={})

    main_request = prompt_meta.main_text.strip() or template.prompt.strip() or args.prompt

    pipeline_directive = _directive("pipeline", "context", "data")

    try:
        pipeline_file = _resolve_pipeline_file(template.scalars, pipeline_directive)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    try:
        pipeline_context, agent_payloads = _load_pipeline_context(pipeline_file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load pipeline context: {exc}", file=sys.stderr)
        sys.exit(1)

    raw_by_agent = agent_payloads.get("raw_by_agent", {})

    directives_map = {
        "global": _block_copy(prompt_meta.blocks.get("global")),
        "strategy": _directive("strategy", "blueprint"),
        "hook": _directive("hook", "angles"),
        "writing": _directive("writing", "draft"),
        "quality": _directive("quality", "qa"),
    }

    crew = WritingAgentCrew()
    result = crew.run(
        user_request=main_request,
        pipeline_context=pipeline_context,
        data_triage_raw=agent_payloads.get("data_triage_raw")
        or _find_agent_raw(raw_by_agent, ["data", "triage"]),
        trend_analysis_raw=agent_payloads.get("trend_analysis_raw")
        or _find_agent_raw(raw_by_agent, ["trend", "analysis"]),
        brand_alignment_raw=agent_payloads.get("brand_alignment_raw")
        or _find_agent_raw(raw_by_agent, ["brand", "alignment"]),
        topic_curator_raw=agent_payloads.get("topic_curator_raw")
        or _find_agent_raw(raw_by_agent, ["topic", "curator"], match_any=True),
        dataset_id=pipeline_context.get("dataset_id"),
        directives=directives_map,
    )

    saved_path = persist_result_if_json(result, output_root, stem="writing_agent")
    payload = coerce_json_payload(result)
    print(serialize_result(result))
    if saved_path is not None:
        print(f"Saved output to {saved_path}", file=sys.stderr)
        if (
            args.export_raw_articles
            and isinstance(payload, dict)
        ):
            raw_payload = payload.get("raw")
            exported_files: List[Path] = []
            if raw_payload:
                try:
                    exported_files = _export_articles_from_raw(raw_payload, saved_path)
                except OSError as exc:
                    print(
                        f"Failed to export platform articles: {exc}",
                        file=sys.stderr,
                    )
            if exported_files:
                export_dir = saved_path.with_suffix("")
                print(
                    f"Exported {len(exported_files)} article text files to {export_dir}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - runtime guard
        print(f"Failed to execute Writing Agent: {exc}", file=sys.stderr)
        sys.exit(1)
