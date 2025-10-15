"""Command-line entry point for the Content Opportunity Pipeline."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CONTENT_PIPELINE_FORCE_OFFLINE", "0")

from cli_common import (
    DirectiveBlock,
    coerce_json_payload,
    load_config,
    parse_prompt_directives,
    persist_result_if_json,
    resolve_prompt,
    serialize_result,
    write_output,
)
from crews.content_opportunity_pipeline import ContentOpportunityPipelineCrew


CONFIG_PATH = Path(__file__).with_name("content_pipeline_config.json")
DEFAULT_BRAND_KB_FILENAME = "Brand_Core_Knowledge_Base_for_justka.ai.yml"
DEFAULT_PROMPTS = {
    "1": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "content_opportunity_pipeline",
        "task": "content_pipeline_default",
    },
    "2": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "content_opportunity_pipeline",
        "task": "content_pipeline_v2",
    },
    "3": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "content_opportunity_pipeline",
        "task": "content_pipeline_v3",
    },
    "4": {
        "path": Path(__file__).with_name("Default_Tasks1.YML"),
        "agent": "content_opportunity_pipeline",
        "task": "content_pipeline_v4",
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
    directive_block: Optional[DirectiveBlock],
) -> Optional[Path]:
    if cli_value:
        return Path(cli_value)

    if directive_block:
        directive_path = (
            directive_block.parameters.get("brand_knowledge_base")
            or directive_block.parameters.get("brand_kb")
            or directive_block.parameters.get("brand_kb_path")
            or directive_block.parameters.get("kb_path")
        )
        if isinstance(directive_path, str) and directive_path.strip():
            return Path(directive_path.strip())

    config_path = config.get("brand_knowledge_base")
    if isinstance(config_path, str) and config_path.strip():
        return Path(config_path)

    scalar_path = template_scalars.get("brand_knowledge_base")
    if scalar_path:
        return Path(scalar_path)
    return None


def _extract_brand_context(brand_knowledge_base: Optional[str]) -> Tuple[str, List[str]]:
    """Derive a friendly brand name and a shortlist of priority topics."""

    if not brand_knowledge_base:
        return "Default Brand", [
            "Customer Experience Automation",
            "Team Collaboration",
            "Lifecycle Marketing",
        ]

    brand_name = "Default Brand"
    topics: List[str] = []

    for line in brand_knowledge_base.splitlines():
        stripped = line.strip()
        if stripped.startswith("brand:"):
            _, value = stripped.split(":", 1)
            brand_name = value.strip().strip("'\"") or brand_name
        elif stripped.startswith("- topic:"):
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                topic_value = parts[1].strip().strip("'\"")
                if topic_value:
                    topics.append(topic_value)
        if len(topics) >= 5:
            break

    if not topics:
        topics = [
            "Customer Experience Automation",
            "Team Collaboration",
            "Lifecycle Marketing",
        ]

    return brand_name, topics[:5]


def _offline_pipeline_result(
    *,
    user_request: str,
    brand_knowledge_base: Optional[str],
    error: Exception,
) -> Dict[str, Any]:
    """Generate a deterministic offline result when the crew cannot run."""

    timestamp = datetime.now(timezone.utc)
    iso_timestamp = timestamp.isoformat().replace("+00:00", "Z")
    dataset_id = f"offline-demo-{timestamp.strftime('%Y%m%d%H%M%S')}"
    trend_report_id = f"{dataset_id}-trend-report"
    brand_name, brand_topics = _extract_brand_context(brand_knowledge_base)

    clusters: List[Dict[str, Any]] = []
    opportunities: List[Dict[str, Any]] = []
    topic_entries: List[Dict[str, Any]] = []

    for index, topic in enumerate(brand_topics[:3], start=1):
        cluster_id = f"offline_cluster_{index:02d}"
        keywords = [topic, "Reddit audience insight", brand_name]
        representative_post_id = f"offline-post-{index:02d}"

        cluster_payload = {
            "cluster_id": cluster_id,
            "core_keywords": keywords,
            "representative_post_ids": [representative_post_id],
            "sentiment_label": "Positive" if index == 1 else "Mixed",
            "trend_velocity": round(0.65 + 0.1 * (3 - index), 2),
            "trend_acceleration": round(0.18 + 0.05 * (3 - index), 2),
            "key_opinion_leaders": ["offline_user_ai_insider", "offline_user_growthmarketer"],
            "lifecycle_stage": "Emerging" if index < 3 else "Mature",
        }
        clusters.append(cluster_payload)

        opportunity_payload = {
            "cluster_id": cluster_id,
            "core_keywords": keywords,
            "representative_post_ids": [representative_post_id],
            "sentiment_label": cluster_payload["sentiment_label"],
            "trend_velocity": cluster_payload["trend_velocity"],
            "trend_acceleration": cluster_payload["trend_acceleration"],
            "key_opinion_leaders": cluster_payload["key_opinion_leaders"],
            "lifecycle_stage": cluster_payload["lifecycle_stage"],
            "relevance_score": round(0.82 + 0.05 * (3 - index), 2),
            "audience_alignment_score": round(0.78 + 0.04 * (3 - index), 2),
            "funnel_stage": "MOFU" if index == 1 else "TOFU",
            "risk_level": "Low" if index != 3 else "Medium",
        }
        opportunities.append(opportunity_payload)

        topic_entries.append(
            {
                "topic_title": f"{brand_name}: {topic}",
                "recommended_angles": [
                    f"Case study: How {brand_name} customers apply {topic}",
                    f"Playbook: Using {topic} to improve conversion and automation",
                    f"KPI spotlight: Measuring the impact of {topic} on revenue and service efficiency",
                ],
                "target_funnel_stage": opportunity_payload["funnel_stage"],
                "key_insights": [
                    f"Dataset {dataset_id} highlights rising engagement around {topic} (e.g., {representative_post_id}).",
                    f"{brand_name}'s positioning emphasises {topic} as a lever for measurable growth and efficiency.",
                ],
                "reference_links": [
                    f"https://reddit.com/r/artificial/comments/{representative_post_id}",
                ],
                "strategic_priority_score": round(0.86 + 0.03 * (3 - index), 2),
            }
        )

    return {
        "status": "offline_fallback",
        "reason": f"Crew execution unavailable: {error.__class__.__name__}: {error}",
        "inputs": {
            "user_request": user_request,
            "brand_knowledge_base_provided": bool(brand_knowledge_base),
        },
        "output": {
            "dataset": {
                "dataset_id": dataset_id,
                "source_files": [],
                "item_count_estimate": 45,
                "notes": "This payload was generated locally because the remote LLM pipeline is unavailable.",
            },
            "trend_report": {
                "dataset_id": dataset_id,
                "generated_at": iso_timestamp,
                "clusters": clusters,
            },
            "scored_opportunities": {
                "source_report_id": trend_report_id,
                "dataset_id": dataset_id,
                "opportunities": opportunities,
            },
            "prioritized_topic_brief": {
                "generated_at": iso_timestamp,
                "source_opportunity_reference": trend_report_id,
                "selected_topics": topic_entries,
            },
        },
    }


def _should_use_offline_mode() -> bool:
    """Determine whether the CLI should bypass the remote crew execution."""

    if os.environ.get("CONTENT_PIPELINE_FORCE_OFFLINE") == "1":
        return True
    if not os.environ.get("GEMINI_API_KEY"):
        return True
    return False


def _extract_stage_artifacts(payload: Any) -> Dict[str, Dict[str, Any]]:
    """Pull out Trend Analysis and Brand Alignment artifacts when available."""

    artifacts: Dict[str, Dict[str, Any]] = {}
    if not isinstance(payload, dict):
        return artifacts

    def _coerce_stage_payload(value: Any) -> Optional[Dict[str, Any]]:
        parsed = coerce_json_payload(value)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(value, str):
            stripped = value.strip()
            if "```" in stripped:
                after_fence = stripped.split("```", 1)[1]
                stripped = after_fence.split("```", 1)[0]
            stripped = stripped.strip()
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].lstrip(":").strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    candidate = json.loads(stripped)
                    if isinstance(candidate, dict):
                        return candidate
                except json.JSONDecodeError:
                    pass
        return None

    def _add_if_dict(key: str, alias: str, source: Dict[str, Any]) -> None:
        value = source.get(key)
        if isinstance(value, dict):
            artifacts.setdefault(alias, value)
        else:
            coerced = _coerce_stage_payload(value)
            if coerced is not None:
                artifacts.setdefault(alias, coerced)

    _add_if_dict("identified_trends_report", "trend_analysis", payload)
    _add_if_dict("scored_and_filtered_opportunities", "brand_alignment", payload)

    output_block = payload.get("output")
    if isinstance(output_block, dict):
        _add_if_dict("trend_report", "trend_analysis", output_block)
        _add_if_dict("scored_opportunities", "brand_alignment", output_block)

    crew_payload = payload.get("crew_output")
    if not isinstance(crew_payload, dict):
        crew_payload = payload

    tasks_output = crew_payload.get("tasks_output")
    if isinstance(tasks_output, list):
        for task in tasks_output:
            if not isinstance(task, dict):
                continue
            agent_name = str(task.get("agent", ""))
            artifact_candidate: Optional[Dict[str, Any]] = None
            for key in ("json_dict", "pydantic", "raw"):
                artifact_candidate = _coerce_stage_payload(task.get(key))
                if isinstance(artifact_candidate, dict):
                    break
                artifact_candidate = None
            if not isinstance(artifact_candidate, dict):
                continue
            if agent_name == "Trend Analysis Agent":
                artifacts.setdefault("trend_analysis", artifact_candidate)
            elif agent_name == "Brand Alignment Agent":
                artifacts.setdefault("brand_alignment", artifact_candidate)

    return artifacts


def _persist_stage_artifacts(
    result: Any,
    output_root: Path,
    final_path: Optional[Path],
) -> List[Path]:
    """Persist Trend Analysis and Brand Alignment artifacts alongside the final report."""

    payload = coerce_json_payload(result)
    if payload is None:
        return []

    artifacts = _extract_stage_artifacts(payload)
    if not artifacts or final_path is None:
        return []

    base_directory = final_path.parent
    filename_root = final_path.name[:-5] if final_path.name.endswith(".json") else final_path.name
    if "_" in filename_root:
        timestamp_prefix = filename_root.split("_", 1)[0]
    else:
        timestamp_prefix = filename_root

    saved_paths: List[Path] = []
    for stage_key, artifact in artifacts.items():
        try:
            target_path = base_directory / f"{timestamp_prefix}_{stage_key}.json"
            write_output(target_path, artifact)
            saved_paths.append(target_path)
        except OSError:
            continue
    return saved_paths


def _resolve_brand_knowledge_base(
    *,
    cli_value: Optional[str],
    config: Dict[str, Any],
    template_scalars: Dict[str, Optional[str]],
    directive_block: Optional[DirectiveBlock],
) -> Optional[str]:
    """Return the brand knowledge base content, falling back to the project default."""

    base_dir = Path(__file__).resolve().parent
    kb_path = _determine_brand_kb_path(cli_value, config, template_scalars, directive_block)
    if kb_path is not None:
        resolved_path = kb_path if kb_path.is_absolute() else base_dir / kb_path
        if not resolved_path.exists():
            print(f"Brand knowledge base not found: {resolved_path}", file=sys.stderr)
            sys.exit(1)
        return _load_brand_knowledge_base(resolved_path)

    default_path = base_dir / DEFAULT_BRAND_KB_FILENAME
    if default_path.exists():
        try:
            return _load_brand_knowledge_base(default_path)
        except RuntimeError:
            # Surface errors for explicit paths, but allow fallback to continue silently.
            pass
    return None


def main() -> None:
    args = parse_args()
    config = load_config(CONFIG_PATH)
    output_root = Path(config.get("output_root", "content_pipeline_outputs"))

    template = resolve_prompt(args.prompt, DEFAULT_PROMPTS)
    prompt_meta = parse_prompt_directives(template.prompt)

    def _block_copy(block: Optional[DirectiveBlock]) -> DirectiveBlock:
        if block is None:
            return DirectiveBlock(instructions="", parameters={})
        return DirectiveBlock(
            instructions=block.instructions,
            parameters=dict(block.parameters),
        )

    global_block = _block_copy(prompt_meta.blocks.get("global"))

    def _directive(*names: str) -> DirectiveBlock:
        for name in names:
            block = prompt_meta.blocks.get(name)
            if block and (block.instructions.strip() or block.parameters):
                return _block_copy(block)
        return DirectiveBlock(instructions="", parameters={})

    main_request = prompt_meta.main_text.strip() or template.prompt.strip() or args.prompt

    brand_knowledge_base = _resolve_brand_knowledge_base(
        cli_value=args.brand_knowledge_base,
        config=config,
        template_scalars=template.scalars,
        directive_block=_directive("config", "brand", "settings"),
    )

    directives_map = {
        "global": global_block,
        "data_triage": _directive("data_triage", "triage", "triage_agent"),
        "trend_analysis": _directive("trend_analysis", "trends", "analysis"),
        "brand_alignment": _directive("brand_alignment", "alignment", "scoring"),
        "topic_curator": _directive("topic_curator", "curator", "briefing"),
    }

    if _should_use_offline_mode():
        print(
            "Remote LLM credentials not detected. Running content pipeline in offline demo mode.",
            file=sys.stderr,
        )
        result = _offline_pipeline_result(
            user_request=main_request,
            brand_knowledge_base=brand_knowledge_base,
            error=RuntimeError("offline_mode"),
        )
    else:
        crew = ContentOpportunityPipelineCrew()
        try:
            result = crew.run(
                user_request=main_request,
                brand_knowledge_base=brand_knowledge_base,
                directives=directives_map,
            )
        except Exception as exc:  # pragma: no cover - runtime guard
            print(
                "Failed to execute crew, using offline fallback result instead.",
                file=sys.stderr,
            )
            result = _offline_pipeline_result(
                user_request=main_request,
                brand_knowledge_base=brand_knowledge_base,
                error=exc,
            )

    saved_path = persist_result_if_json(result, output_root, stem="content_opportunity_pipeline")
    stage_paths = _persist_stage_artifacts(result, output_root, saved_path)
    print(serialize_result(result))
    if saved_path is not None:
        print(f"Saved output to {saved_path}", file=sys.stderr)
    for path in stage_paths:
        print(f"Saved stage output to {path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - runtime guard
        print(f"Failed to execute Content Opportunity Pipeline: {exc}", file=sys.stderr)
        sys.exit(1)
