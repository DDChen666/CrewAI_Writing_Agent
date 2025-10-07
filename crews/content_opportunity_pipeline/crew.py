"""Crew entry-point for the Content Opportunity Pipeline."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from crewai import Crew

from .agents import (
    build_brand_alignment_agent,
    build_data_triage_agent,
    build_topic_curator_agent,
    build_trend_analysis_agent,
)
from .tasks import (
    build_brand_alignment_task,
    build_data_triage_task,
    build_topic_curator_task,
    build_trend_analysis_task,
)


def _strip_code_fence(raw: str) -> str:
    """Remove leading and trailing Markdown code fences if present."""

    stripped = raw.strip()
    if not stripped.startswith("```"):
        return stripped

    newline_index = stripped.find("\n")
    if newline_index != -1:
        stripped = stripped[newline_index + 1 :]
    else:  # opening fence without newline payload
        return ""

    if stripped.endswith("```"):
        stripped = stripped[:-3]
    elif "\n```" in stripped:
        stripped = stripped.rsplit("\n```", 1)[0]
    return stripped.strip()


def _parse_json_field(payload: Any) -> Optional[Any]:
    """Best-effort conversion of a task payload into JSON data."""

    if payload is None:
        return None
    if isinstance(payload, (dict, list)):
        return payload
    if isinstance(payload, str):
        candidate = _strip_code_fence(payload)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None
    if hasattr(payload, "model_dump"):
        try:
            return payload.model_dump()
        except Exception:  # pragma: no cover - defensive
            return None
    return None


def _extract_task_artifact(task_blob: Dict[str, Any]) -> Optional[Any]:
    """Extract a structured artifact from a crew task output."""

    for key in ("json_dict", "pydantic", "raw"):
        artifact = _parse_json_field(task_blob.get(key))
        if artifact is not None:
            return artifact
    return None


def _build_pipeline_payload(result: Any) -> Optional[Dict[str, Any]]:
    """Normalise the crew output and surface the key agent deliverables."""

    if isinstance(result, dict):
        payload: Dict[str, Any] = result
    elif hasattr(result, "model_dump"):
        try:
            payload = result.model_dump()
        except Exception:  # pragma: no cover - defensive
            return None
    else:
        return None

    tasks_output = payload.get("tasks_output")
    if not isinstance(tasks_output, list):
        return None

    tasks_by_agent = {
        str(task.get("agent")): task
        for task in tasks_output
        if isinstance(task, dict) and task.get("agent")
    }

    trend_report = _extract_task_artifact(tasks_by_agent.get("Trend Analysis Agent", {}))
    opportunities = _extract_task_artifact(tasks_by_agent.get("Brand Alignment Agent", {}))
    topic_brief = _extract_task_artifact(tasks_by_agent.get("Topic Curator Agent", {}))

    # Ensure we only return an enriched payload when all key artifacts are present.
    if not all((trend_report, opportunities, topic_brief)):
        return None

    enriched: Dict[str, Any] = {
        "identified_trends_report": trend_report,
        "scored_and_filtered_opportunities": opportunities,
        "prioritized_topic_brief": topic_brief,
        "crew_output": payload,
    }
    return enriched


class ContentOpportunityPipelineCrew:
    """High-level orchestrator that runs the content opportunity workflow."""

    def __init__(self) -> None:
        data_triage_agent = build_data_triage_agent()
        trend_analysis_agent = build_trend_analysis_agent()
        brand_alignment_agent = build_brand_alignment_agent()
        topic_curator_agent = build_topic_curator_agent()

        data_triage_task = build_data_triage_task(data_triage_agent)
        trend_analysis_task = build_trend_analysis_task(trend_analysis_agent, data_triage_task)
        brand_alignment_task = build_brand_alignment_task(brand_alignment_agent, trend_analysis_task)
        topic_curator_task = build_topic_curator_task(topic_curator_agent, brand_alignment_task)

        self.crew = Crew(
            agents=[
                data_triage_agent,
                trend_analysis_agent,
                brand_alignment_agent,
                topic_curator_agent,
            ],
            tasks=[
                data_triage_task,
                trend_analysis_task,
                brand_alignment_task,
                topic_curator_task,
            ],
            verbose=True,
        )

    def run(
        self,
        *,
        user_request: str,
        brand_knowledge_base: str | None = None,
    ) -> Any:
        """Execute the pipeline with the supplied inputs."""

        inputs = {"user_request": user_request}
        if brand_knowledge_base is not None:
            inputs["brand_knowledge_base"] = brand_knowledge_base
        result = self.crew.kickoff(inputs=inputs)

        enriched_payload = _build_pipeline_payload(result)
        return enriched_payload if enriched_payload is not None else result


__all__ = ["ContentOpportunityPipelineCrew"]
