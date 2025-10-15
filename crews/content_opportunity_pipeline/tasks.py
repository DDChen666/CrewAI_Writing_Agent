"""Task definitions for the Content Opportunity Pipeline crew."""
from __future__ import annotations

from typing import Dict, Optional

from crewai import Task

from .schemas import (
    IdentifiedTrendsReport,
    PrioritizedTopicBrief,
    ScoredAndFilteredOpportunities,
)


def _append_operator_context(
    base_description: str,
    instructions: str = "",
    parameters: Optional[Dict[str, str]] = None,
) -> str:
    segments = [base_description.rstrip()]
    detail_blocks = []
    if parameters:
        formatted = "\n".join(
            f"- {key}: {value}" for key, value in parameters.items()
        )
        detail_blocks.append(f"Configured parameters:\n{formatted}")
    if instructions.strip():
        detail_blocks.append(f"Operator directives:\n{instructions.strip()}")
    if detail_blocks:
        segments.append("\n\n".join(detail_blocks))
    return "\n\n".join(segments).strip()


def build_data_triage_plan_task(
    agent,
    *,
    instructions: str = "",
    parameters: Optional[Dict[str, str]] = None,
) -> Task:
    """Task guiding the Data Triage Manager to assemble the dataset and preview plan."""

    base_description = (
        "Interpret the operator request '{{user_request}}' and coordinate the Reddit triage tools without ever loading raw content. "
        "When a path like 'scraper_outputs/20251015/*.json' is provided, split it into base_dir ('scraper_outputs'), optional subdirectories, "
        "and date_prefixes=['20251015'] before calling tools. Use reddit_scrape_locator to enumerate candidate files, verifying that the "
        "resolved directory exists and adjusting parameters instead of guessing. Only proceed when locator returns files. Then use reddit_scrape_loader "
        "to normalise them, and immediately call "
        "reddit_dataset_export_tool to persist the dataset to SQLite with full fidelity before applying any optional filtering. "
        "Apply additional filters only when explicitly instructed; otherwise hand off the complete export. If locator returns no files, stop, capture the failure "
        "and do not attempt loader or exporter calls until corrected inputs exist. Capture the dataset_id returned "
        "by the export tool the moment it is generated and track it for your report. Always apply explicit limits when sampling so downstream agents "
        "expand datasets via lookup tools rather than relying on oversized previews. Maintain a running checklist so you can state which files were loaded, "
        "which filters (if any) were applied, and exactly which dataset_id was persisted. After the dataset is ready, design one or more scoped preview requests "
        "for specialist Content Previewers, each with strict boundaries on tool, filter criteria, requested `fields` and maximum sample size (never exceed 20 items per request). "
        "Do not call content_explorer or reddit_dataset_lookup yourself; your role is planning and delegation only."
    )

    description = _append_operator_context(
        base_description,
        instructions=instructions,
        parameters=parameters,
    )

    return Task(
        description=description,
        expected_output=(
            "Return JSON describing the dataset you prepared and the preview missions you are delegating. Include dataset_id, source_files, "
            "subreddit coverage, item_count, key filtering rules applied, and a brief plan_summary. Provide a preview_requests array where each entry specifies "
            "request_id, dataset_id, strategy label (e.g., 'top_k', 'stratified_subreddit', 'time_window'), a concise description, the intended tool, "
            "parameters (including explicit limits ≤ 20), and the insight_focus you expect back. Keep the response compact and free of raw post content. "
            "When no files are located, set status to 'error', leave preview_requests empty, surface the failure in plan_summary, and skip downstream tool calls. "
            "Your final answer must be a single JSON object following the DataTriagePreviewPlan schema with a populated dataset_id value and no additional commentary."
        ),
        agent=agent,
        async_execution=False,
        output_json_schema={
            "name": "DataTriagePreviewPlan",
            "schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "dataset_id": {"type": "string"},
                    "source_files": {"type": "array", "items": {"type": "string"}},
                    "subreddits": {"type": "array", "items": {"type": "string"}},
                    "item_count": {"type": "integer"},
                    "filters": {"type": "array", "items": {"type": "string"}},
                    "plan_summary": {"type": "string"},
                    "preview_requests": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "request_id": {"type": "string"},
                                "dataset_id": {"type": "string"},
                                "strategy": {"type": "string"},
                                "description": {"type": "string"},
                                "tool": {"type": "string"},
                                "parameters": {"type": "object"},
                                "sample_size_limit": {"type": "integer"},
                                "insight_focus": {"type": "string"},
                            },
                            "required": [
                                "request_id",
                                "dataset_id",
                                "strategy",
                                "parameters",
                                "sample_size_limit",
                            ],
                        },
                    },
                },
                "required": [
                    "status",
                    "dataset_id",
                    "source_files",
                    "item_count",
                    "preview_requests",
                ],
            },
        },
    )


def build_content_preview_task(
    agent,
    plan_task: Task,
    *,
    instructions: str = "",
    parameters: Optional[Dict[str, str]] = None,
) -> Task:
    """Task guiding the Content Previewer to execute scoped content sampling."""

    base_description = (
        "You receive the Data Triage Manager's preview plan describing dataset_id and preview_requests. "
        "If status is 'error' or dataset_id is blank, acknowledge the failure and skip tool usage entirely. For valid requests use only the approved tool "
        "(content explorer or dataset lookup) with the provided parameters. When calling reddit_dataset_lookup, explicitly set the `fields` parameter so responses stay lean, "
        "defaulting to the built-in minimal payload unless richer data is essential, and never request ['*'] unless the manager has signed off. Never exceed the stated sample_size_limit "
        "or fetch raw post bodies beyond what the tool returns. Summarise findings per request: include high-level metrics (averages, medians, standout values), "
        "recurring themes or keywords, notable post_ids worth escalation, and any red_flags or data quality issues. If a request would breach safety constraints, "
        "scale it down or report the limitation instead of over-fetching. Keep your reasoning lightweight and avoid embedding entire posts."
    )

    description = _append_operator_context(
        base_description,
        instructions=instructions,
        parameters=parameters,
    )

    return Task(
        description=description,
        expected_output=(
            "Respond with JSON conforming to the ContentPreviewFindings schema. Echo the dataset_id, set status to reflect success or issues, "
            "and provide a completed_requests array where each entry contains request_id, sampled_post_ids (≤ sample_size_limit), key_metrics, "
            "notable_topics, red_flags, and follow_up_recommendations. Add a global_observations field for cross-request patterns. "
            "If no preview_requests were supplied, set status to 'error' or 'blocked', leave completed_requests empty, and explain why tools were skipped. "
            "Your final answer must be a single JSON object with no surrounding commentary."
        ),
        agent=agent,
        context=[plan_task],
        async_execution=False,
        output_json_schema={
            "name": "ContentPreviewFindings",
            "schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "dataset_id": {"type": "string"},
                    "global_observations": {"type": "string"},
                    "completed_requests": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "request_id": {"type": "string"},
                                "sampled_post_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "key_metrics": {"type": "object"},
                                "notable_topics": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "red_flags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "follow_up_recommendations": {"type": "string"},
                            },
                            "required": [
                                "request_id",
                                "sampled_post_ids",
                                "key_metrics",
                                "notable_topics",
                            ],
                        },
                    },
                },
                "required": ["status", "dataset_id", "completed_requests"],
            },
        },
    )


def build_data_triage_summary_task(
    agent,
    plan_task: Task,
    preview_task: Task,
    *,
    instructions: str = "",
    parameters: Optional[Dict[str, str]] = None,
) -> Task:
    """Task guiding the Data Triage Manager to aggregate preview findings into the final hand-off."""

    base_description = (
        "Review your original preview plan alongside the Content Previewer findings. "
        "If the plan recorded an error (e.g., no files found), acknowledge it and document remediation steps instead of attempting additional tool calls. "
        "Otherwise integrate metadata, sampling insights and any outstanding risks into the final Cleaned_Content_Stream hand-off for downstream agents. "
        "Highlight dataset_id, source files, item_count, subreddits involved, filters applied, and concise recommendations that reflect preview discoveries. "
        "Explicitly flag preview_truncated or focus_view_truncated when applicable so the Trend Analysis Agent knows whether to fetch more data."
    )

    description = _append_operator_context(
        base_description,
        instructions=instructions,
        parameters=parameters,
    )

    return Task(
        description=description,
        expected_output=(
            "Return JSON describing the dataset you prepared, including dataset_id, source_files, subreddit coverage, "
            "item_count, key filtering rules applied, and recommendations for the next stage. Summarise preview insights without embedding raw posts: "
            "surface notable themes, standout post_ids and any risks the next agent should examine with lookup tools. Explicitly note preview_truncated or "
            "focus_view_truncated flags when sample limits were hit. Your final answer must be a single JSON object that conforms to the CleanedContentStreamSummary "
            "schema with a populated dataset_id value and no additional commentary."
        ),
        agent=agent,
        context=[plan_task, preview_task],
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
                    "preview_truncated": {"type": "boolean"},
                    "focus_view_truncated": {"type": "boolean"},
                    "next_steps": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": [
                    "status",
                    "dataset_id",
                    "source_files",
                    "item_count",
                ],
            },
        },
    )


def build_trend_analysis_task(
    agent,
    data_triage_summary_task: Task,
    *,
    instructions: str = "",
    parameters: Optional[Dict[str, str]] = None,
) -> Task:
    """Task guiding the Trend Analysis Agent."""

    base_description = (
        "Analyse the Cleaned_Content_Stream dataset surfaced by the triage manager. Use the dataset lookup tool when "
        "you need to inspect specific posts, always constraining responses by setting explicit `fields` (or using the default minimal payload) so outputs stay lightweight. "
        "Cluster the conversation, estimate momentum metrics and sentiment, "
        "quantify confidence in each metric, and summarise clusters for downstream consumers using the IdentifiedTrendsReport schema. "
        "Preserve the upstream dataset_id in every deliverable so downstream agents can join records accurately."
    )

    description = _append_operator_context(
        base_description,
        instructions=instructions,
        parameters=parameters,
    )

    return Task(
        description=description,
        expected_output=(
            "Respond with JSON that can be parsed as an IdentifiedTrendsReport, including dataset_id, generated_at and an array of clusters. "
            "When upstream previews are truncated, request additional context via dataset lookup or the content explorer before expanding your response. "
            "Your final answer must be valid JSON conforming exactly to the IdentifiedTrendsReport schema with no surrounding narrative."
        ),
        agent=agent,
        context=[data_triage_summary_task],
        async_execution=False,
        output_json_schema=IdentifiedTrendsReport.model_json_schema(),
    )


def build_brand_alignment_task(
    agent,
    trend_analysis_task: Task,
    *,
    instructions: str = "",
    parameters: Optional[Dict[str, str]] = None,
) -> Task:
    """Task guiding the Brand Alignment Agent."""

    base_description = (
        "Use '{{brand_knowledge_base}}' to evaluate each trend cluster for brand fit, ICP alignment and risk. Ensure "
        "scores are justified with qualitative rationale, call reddit_dataset_lookup for deeper dives (while constraining results with explicit `fields` selections), and emit a "
        "ScoredAndFilteredOpportunities payload ordered by strategic value. Note any assumptions made when the knowledge base "
        "is silent and highlight disqualifying risks when declining an opportunity. Carry forward the originating report identifiers "
        "from upstream outputs so results stay linkable."
    )

    description = _append_operator_context(
        base_description,
        instructions=instructions,
        parameters=parameters,
    )

    return Task(
        description=description,
        expected_output=(
            "Return JSON that adheres to the ScoredAndFilteredOpportunities schema, including the originating report identifier and ranked opportunities. "
            "Your final answer must be a single JSON object that matches the schema exactly, without markdown wrappers."
        ),
        agent=agent,
        context=[trend_analysis_task],
        async_execution=False,
        output_json_schema=ScoredAndFilteredOpportunities.model_json_schema(),
    )


def build_topic_curator_task(
    agent,
    brand_alignment_task: Task,
    *,
    instructions: str = "",
    parameters: Optional[Dict[str, str]] = None,
) -> Task:
    """Task guiding the Topic Curator Agent."""

    base_description = (
        "Select the highest leverage opportunities from the brand alignment stage and craft production-ready briefs. "
        "For each topic provide title, 3-5 editorial angles, funnel focus, supporting insights and reference links. "
        "Highlight the decision criteria for each selection and flag any open risks or validation tasks required before publishing. "
        "Retain traceability back to upstream dataset and opportunity identifiers in every brief."
    )

    description = _append_operator_context(
        base_description,
        instructions=instructions,
        parameters=parameters,
    )

    return Task(
        description=description,
        expected_output=(
            "Produce JSON following the PrioritizedTopicBrief schema, citing which opportunities were selected and why. "
            "Finalise with a single JSON object matching the schema exactly; omit extra commentary."
        ),
        agent=agent,
        context=[brand_alignment_task],
        async_execution=False,
        output_json_schema=PrioritizedTopicBrief.model_json_schema(),
    )


__all__ = [
    "build_data_triage_plan_task",
    "build_content_preview_task",
    "build_data_triage_summary_task",
    "build_trend_analysis_task",
    "build_brand_alignment_task",
    "build_topic_curator_task",
]
