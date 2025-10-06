"""Crew entry-point for the Content Opportunity Pipeline."""
from __future__ import annotations

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

    def run(self, *, user_request: str, brand_knowledge_base: str | None = None) -> str:
        """Execute the pipeline with the supplied inputs."""

        inputs = {"user_request": user_request}
        if brand_knowledge_base is not None:
            inputs["brand_knowledge_base"] = brand_knowledge_base
        return self.crew.kickoff(inputs=inputs)


__all__ = ["ContentOpportunityPipelineCrew"]
