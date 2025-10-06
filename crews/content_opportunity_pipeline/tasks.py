"""Task definitions for the Content Opportunity Pipeline crew."""
from __future__ import annotations

from crewai import Task

from .schemas import (
    IdentifiedTrendsReport,
    PrioritizedTopicBrief,
    ScoredAndFilteredOpportunities,
)


def build_data_triage_task(agent) -> Task:
    """Task guiding the Data Triage Agent."""

    return Task(
        description=(
            "Interpret the operator request '{{user_request}}' and coordinate the Reddit triage tools. "
            "Use reddit_scrape_locator to list candidate files, reddit_scrape_loader to normalise them, "
            "and reddit_dataset_filter/reddit_dataset_exporter to produce a Cleaned_Content_Stream dataset."
        ),
        expected_output=(
            "Return JSON describing the dataset you prepared, including dataset_id, source_files, subreddit coverage, "
            "item_count, key filtering rules applied, and recommendations for the next stage."
        ),
        agent=agent,
        async_execution=False,
        output_json_schema={
            "name": "CleanedContentStreamSummary",
            "schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "dataset_id": {"type": "string"},
                    "source_files": {"type": "array", "items": {"type": "string"}},
                    "subreddits": {"type": "array", "items": {"type": "string"}},
                    "item_count": {"type": "integer"},
                    "filters": {"type": "array", "items": {"type": "string"}},
                    "next_steps": {"type": "string"},
                },
                "required": ["status", "dataset_id", "source_files", "item_count"],
            },
        },
    )


def build_trend_analysis_task(agent, data_triage_task: Task) -> Task:
    """Task guiding the Trend Analysis Agent."""

    return Task(
        description=(
            "Analyse the Cleaned_Content_Stream dataset surfaced by the triage agent. Use the dataset lookup tool when "
            "you need to inspect specific posts. Cluster the conversation, estimate momentum metrics and sentiment, and "
            "summarise each cluster for downstream consumers using the IdentifiedTrendsReport schema."
        ),
        expected_output=(
            "Respond with JSON that can be parsed as an IdentifiedTrendsReport, including dataset_id, generated_at and an array of clusters."
        ),
        agent=agent,
        context=[data_triage_task],
        async_execution=False,
        output_json_schema=IdentifiedTrendsReport.model_json_schema(),
    )


def build_brand_alignment_task(agent, trend_analysis_task: Task) -> Task:
    """Task guiding the Brand Alignment Agent."""

    return Task(
        description=(
            "Use '{{brand_knowledge_base}}' to evaluate each trend cluster for brand fit, ICP alignment and risk. Ensure "
            "scores are justified with qualitative rationale, call reddit_dataset_lookup for deeper dives, and emit a "
            "ScoredAndFilteredOpportunities payload ordered by strategic value."
        ),
        expected_output=(
            "Return JSON that adheres to the ScoredAndFilteredOpportunities schema, including the originating report identifier and ranked opportunities."
        ),
        agent=agent,
        context=[trend_analysis_task],
        async_execution=False,
        output_json_schema=ScoredAndFilteredOpportunities.model_json_schema(),
    )


def build_topic_curator_task(agent, brand_alignment_task: Task) -> Task:
    """Task guiding the Topic Curator Agent."""

    return Task(
        description=(
            "Select the highest leverage opportunities from the brand alignment stage and craft production-ready briefs. "
            "For each topic provide title, 3-5 editorial angles, funnel focus, supporting insights and reference links."
        ),
        expected_output=(
            "Produce JSON following the PrioritizedTopicBrief schema, citing which opportunities were selected and why."
        ),
        agent=agent,
        context=[brand_alignment_task],
        async_execution=False,
        output_json_schema=PrioritizedTopicBrief.model_json_schema(),
    )


__all__ = [
    "build_data_triage_task",
    "build_trend_analysis_task",
    "build_brand_alignment_task",
    "build_topic_curator_task",
]
