"""Command-line entry point for the Content Opportunity Pipeline."""
from __future__ import annotations

import argparse
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


def _extract_brand_context(brand_knowledge_base: Optional[str]) -> Tuple[str, List[str]]:
    """Derive a friendly brand name and a shortlist of priority topics."""

    if not brand_knowledge_base:
        return "JustKa AI", [
            "LINE 官方帳號經營",
            "多智慧體協作",
            "標籤分眾與旅程自動化",
        ]

    brand_name = "JustKa AI"
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
            "LINE 官方帳號經營",
            "多智慧體協作",
            "標籤分眾與旅程自動化",
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
        keywords = [topic, "Reddit 用戶洞察", "JustKa AI"]
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
                "topic_title": f"{brand_name}：{topic}",
                "recommended_angles": [
                    f"案例解析：{brand_name} 客戶如何運用 {topic}",
                    f"操作指南：以 {topic} 強化轉單與自動化",
                    f"KPI 對照：{topic} 對營收與客服效率的影響",
                ],
                "target_funnel_stage": opportunity_payload["funnel_stage"],
                "key_insights": [
                    f"資料集 {dataset_id} 中的 {representative_post_id} 顯示受眾對 {topic} 的討論熱度上升。",
                    f"品牌價值主張強調 {topic} 能將客服成本轉為成長動能。",
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

    if _should_use_offline_mode():
        print(
            "Remote LLM credentials not detected. Running content pipeline in offline demo mode.",
            file=sys.stderr,
        )
        result = _offline_pipeline_result(
            user_request=prompt,
            brand_knowledge_base=brand_knowledge_base,
            error=RuntimeError("offline_mode"),
        )
    else:
        crew = ContentOpportunityPipelineCrew()
        try:
            result = crew.run(user_request=prompt, brand_knowledge_base=brand_knowledge_base)
        except Exception as exc:  # pragma: no cover - runtime guard
            print(
                "Failed to execute crew, using offline fallback result instead.",
                file=sys.stderr,
            )
            result = _offline_pipeline_result(
                user_request=prompt,
                brand_knowledge_base=brand_knowledge_base,
                error=exc,
            )

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
