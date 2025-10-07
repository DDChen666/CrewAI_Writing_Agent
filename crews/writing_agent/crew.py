"""Crew entry-point for the Writing Agent workflow."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from crewai import Crew

from .agents import build_writing_agent
from .tasks import build_writing_task


class WritingAgentCrew:
    """High-level orchestrator that generates platform-ready rewrites."""

    def __init__(self) -> None:
        agent = build_writing_agent()
        task = build_writing_task(agent)
        self.crew = Crew(agents=[agent], tasks=[task], verbose=True)

    def _condense_context(self, pipeline_context: Dict[str, Any]) -> str:
        """Return a compact JSON string with only the essentials for prompting.

        Keeps: source_file, dataset_id, top opportunities with short rationales,
        and topic briefs with limited angles and a capped set of reference links.
        """
        try:
            source_file = pipeline_context.get("source_file")
            dataset_id = pipeline_context.get("dataset_id")

            scored = pipeline_context.get("scored_and_filtered_opportunities") or {}
            opps = []
            for opp in (scored.get("opportunities") or [])[:5]:
                topic = opp.get("topic")
                reason = opp.get("reason_for_selection")
                if isinstance(reason, str) and len(reason) > 360:
                    reason = reason[:360] + "…"
                opps.append({"topic": topic, "reason_for_selection": reason})

            briefs = []
            for brief in (pipeline_context.get("prioritized_topic_briefs") or [])[:5]:
                refs = brief.get("reference_links") or []
                angles = brief.get("editorial_angles") or []
                # Truncate angles for brevity
                trimmed_angles = []
                for a in angles[:3]:
                    trimmed_angles.append(a if len(a) <= 240 else a[:240] + "…")
                briefs.append(
                    {
                        "topic_title": brief.get("topic_title"),
                        "funnel_focus": brief.get("funnel_focus"),
                        "editorial_angles": trimmed_angles,
                        "reference_links": refs[:12],
                    }
                )

            compact = {
                "source_file": source_file,
                "dataset_id": dataset_id,
                "scored_and_filtered_opportunities": {"opportunities": opps},
                "prioritized_topic_briefs": briefs,
            }
            return json.dumps(compact, ensure_ascii=False)
        except Exception:
            # Fallback to the minimal pointer if anything unexpected happens
            minimal = {
                "source_file": pipeline_context.get("source_file"),
                "dataset_id": pipeline_context.get("dataset_id"),
            }
            return json.dumps(minimal, ensure_ascii=False)

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
