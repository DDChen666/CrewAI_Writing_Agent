"""Crew entry-point for the Writing Agent workflow."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from crewai import Crew

from .agents import build_writing_team
from .tasks import (
    build_hook_task,
    build_quality_task,
    build_strategy_task,
    build_writing_task,
)


class WritingAgentCrew:
    """High-level orchestrator that generates platform-ready rewrites."""

    def __init__(self) -> None:
        team = build_writing_team()
        strategy_task = build_strategy_task(team["editor_in_chief"])
        hook_task = build_hook_task(team["hook_architect"], strategy_task)
        writing_task = build_writing_task(
            team["master_writer"], strategy_task, hook_task
        )
        quality_task = build_quality_task(
            team["editorial_guardian"], strategy_task, hook_task, writing_task
        )

        self.crew = Crew(
            agents=list(team.values()),
            tasks=[strategy_task, hook_task, writing_task, quality_task],
            verbose=True,
        )
        self.final_task = quality_task

    def _condense_context(self, pipeline_context: Dict[str, Any]) -> str:
        """Return a compact JSON string with only the essentials for prompting.

        Keeps: source_file, dataset_id, top opportunities with short rationales,
        and topic briefs with limited angles and a capped set of reference links.
        """
        def _trim_text(text: Any, limit: int = 480) -> Any:
            if isinstance(text, str) and len(text) > limit:
                return text[:limit] + "…"
            return text

        try:
            source_file = pipeline_context.get("source_file")
            dataset_id = pipeline_context.get("dataset_id")

            scored = pipeline_context.get("scored_and_filtered_opportunities") or {}
            opps = []
            for opp in (scored.get("opportunities") or [])[:5]:
                entry: Dict[str, Any] = {
                    "cluster_id": opp.get("cluster_id"),
                    "name": opp.get("name")
                    or opp.get("topic")
                    or opp.get("topic_title"),
                }
                for score_key in (
                    "brand_fit_score",
                    "icp_alignment_score",
                    "icp_fit_score",
                    "relevance_score",
                    "risk_score",
                    "audience_alignment_score",
                ):
                    if score_key in opp:
                        entry[score_key] = opp.get(score_key)

                qualitative = opp.get("qualitative_rationale") or opp.get(
                    "justification"
                )
                if isinstance(qualitative, dict):
                    entry["qualitative_rationale"] = {
                        key: _trim_text(value)
                        for key, value in qualitative.items()
                        if isinstance(value, str)
                    }

                selection_fields = [
                    "selection_justification",
                    "summary",
                    "reason",
                    "reason_for_selection",
                    "recommendation",
                ]
                for field in selection_fields:
                    value = opp.get(field)
                    if isinstance(value, str) and value.strip():
                        entry[field] = _trim_text(value)
                        break

                action_items = opp.get("actionable_insights") or opp.get(
                    "recommended_actions"
                )
                if isinstance(action_items, list) and action_items:
                    entry["actionable_insights"] = [
                        _trim_text(item) for item in action_items[:5]
                    ]

                opps.append(entry)

            briefs = []
            for brief in (pipeline_context.get("prioritized_topic_briefs") or [])[:5]:
                refs = brief.get("reference_links") or []
                angles = brief.get("editorial_angles") or []
                # Truncate angles for brevity
                trimmed_angles = []
                for a in angles[:3]:
                    trimmed_angles.append(a if len(a) <= 240 else a[:240] + "…")
                funnel_focus = brief.get("funnel_focus")
                if isinstance(funnel_focus, list):
                    funnel_value: Any = funnel_focus[:5]
                else:
                    funnel_value = funnel_focus
                briefs.append(
                    {
                        "topic_title": brief.get("topic_title"),
                        "funnel_focus": funnel_value,
                        "editorial_angles": trimmed_angles,
                        "reference_links": refs[:12],
                        "supporting_insights": [
                            _trim_text(insight)
                            for insight in (brief.get("supporting_insights") or [])[:5]
                        ],
                    }
                )

            curator_notes = pipeline_context.get("prioritized_topic_briefs_notes")
            if isinstance(curator_notes, str):
                curator_notes = _trim_text(curator_notes, limit=640)
            else:
                curator_notes = None

            compact = {
                "source_file": source_file,
                "dataset_id": dataset_id,
                "scored_and_filtered_opportunities": {"opportunities": opps},
                "prioritized_topic_briefs": briefs,
            }
            if curator_notes:
                compact["prioritized_topic_briefs_notes"] = curator_notes
            if isinstance(scored, dict):
                report_id = scored.get("originating_report_id")
                if report_id:
                    compact["scored_and_filtered_opportunities"]["originating_report_id"] = report_id
            return json.dumps(compact, ensure_ascii=False)
        except Exception:
            # Fallback to the minimal pointer if anything unexpected happens
            minimal = {
                "source_file": pipeline_context.get("source_file"),
                "dataset_id": pipeline_context.get("dataset_id"),
            }
            return json.dumps(minimal, ensure_ascii=False)

    def _validate_pipeline_context(self, pipeline_context: Dict[str, Any]) -> None:
        if not isinstance(pipeline_context, dict):
            raise ValueError(
                "WritingAgentCrew requires pipeline_context to be a dictionary."
            )

        missing: list[str] = []

        dataset_id = pipeline_context.get("dataset_id")
        if not isinstance(dataset_id, str) or not dataset_id.strip():
            missing.append("dataset_id")

        briefs = pipeline_context.get("prioritized_topic_briefs")
        if not self._is_non_empty_sequence(briefs):
            missing.append("prioritized_topic_briefs")

        scored = pipeline_context.get("scored_and_filtered_opportunities")
        opportunities = None
        if isinstance(scored, dict):
            opportunities = scored.get("opportunities") or scored.get(
                "scored_opportunities"
            )
        if not self._is_non_empty_sequence(opportunities):
            missing.append("scored_and_filtered_opportunities.opportunities")

        if missing:
            raise ValueError(
                "WritingAgentCrew requires pipeline_context to include: "
                + ", ".join(missing)
            )

    @staticmethod
    def _is_non_empty_sequence(value: Any) -> bool:
        if isinstance(value, (list, tuple, set)):
            return len(value) > 0
        return False

    def run(
        self,
        *,
        user_request: str,
        pipeline_context: Dict[str, Any],
        data_triage_raw: Optional[str] = None,
        trend_analysis_raw: Optional[str] = None,
        brand_alignment_raw: Optional[str] = None,
        topic_curator_raw: Optional[str] = None,
        dataset_id: Optional[str] = None,
    ) -> Any:
        """Execute the crew with the supplied rewrite instructions and context."""

        self._validate_pipeline_context(pipeline_context)

        # Build a condensed prompt context to reduce input token load
        context_json = self._condense_context(pipeline_context)
        inputs = {
            "user_request": user_request,
            "pipeline_context": context_json,
            # Do NOT inline raw logs into the prompt; keep empty to avoid token blowup
            "data_triage_raw": "",
            "trend_analysis_raw": "",
            "brand_alignment_raw": "",
            "topic_curator_raw": "",
            "dataset_id": dataset_id or "",
        }
        return self.crew.kickoff(inputs=inputs)


__all__ = ["WritingAgentCrew"]
