"""Task definitions for the Writing Agent crew."""
from __future__ import annotations

from crewai import Task

from .schemas import WritingAgentOutput


def build_writing_task(agent) -> Task:
    """Task guiding the Writing Agent to produce platform-ready rewrites."""

    return Task(
        description=(
            "Review the condensed context inside '{{pipeline_context}}'. Use the summarized "
            "'scored_and_filtered_opportunities' for strategic positioning and the "
            "'prioritized_topic_briefs' to determine concrete writing tasks. If '{{dataset_id}}' "
            "is provided, call the content_explorer tool with specific post_ids from the briefs' "
            "reference_links to verify quotes and extract material. Apply the rewrite instructions "
            "from '{{user_request}}' (or use the default style guidance when unspecified) and craft "
            "channel-ready copy."
        ),
        expected_output=(
            "Return JSON that conforms to the WritingAgentOutput schema, including platform-specific rewrites, "
            "supporting references and editorial notes for downstream editors."
        ),
        agent=agent,
        async_execution=False,
        output_json_schema=WritingAgentOutput.model_json_schema(),
    )


__all__ = ["build_writing_task"]
