"""Task definitions for the Reddit scraping crew."""
from __future__ import annotations

from typing import Dict, Optional

from crewai import Task


def _append_operator_context(
    base_description: str,
    instructions: str = "",
    parameters: Optional[Dict[str, str]] = None,
) -> str:
    segments = [base_description.rstrip()]
    detail_blocks = []
    if parameters:
        formatted = "\n".join(f"- {key}: {value}" for key, value in parameters.items())
        detail_blocks.append(f"Configured parameters:\n{formatted}")
    if instructions.strip():
        detail_blocks.append(f"Operator directives:\n{instructions.strip()}")
    if detail_blocks:
        segments.append("\n\n".join(detail_blocks))
    return "\n\n".join(segments).strip()


def build_reddit_scraping_task(
    agent,
    *,
    instructions: str = "",
    parameters: Optional[Dict[str, str]] = None,
) -> Task:
    """Create the main task that interprets user intent."""
    base_description = (
        "You receive a natural language request that describes what Reddit data "
        "should be fetched. The request to satisfy is: '{{user_request}}'. "
        "Decide which API endpoints or tools to call to fulfil the request. Always "
        "prefer the structured reddit_subreddit_fetcher tool for subreddit listings "
        "or user submitted-post histories, and pass a JSON object containing: "
        "subreddit (string identifier such as 'r/python' or 'u/spez'), limit, sort, "
        "time_filter (only when sort='top' or 'best'), comment_depth (0-10 or 'all' "
        "to fully expand), skip_media, and timeout. Interpret 'best' as 'top' and "
        "default its time_filter to 'day'; note this correction in the final "
        "request_summary. Use reddit_api_gateway when profile metadata (e.g. "
        "GET /user/<username>/about) or other non-listing endpoints are required; "
        "combine it with the structured tool when both posts and profile details "
        "are needed. Always provide tool arguments as JSON dictionaries, and you "
        "may chain multiple tool calls to satisfy the request. When the user asks "
        "for 'all comments', invoke the subreddit tool with comment_depth='all' so "
        "the scraper expands every thread until no 'more' remain."
    )

    description = _append_operator_context(
        base_description,
        instructions=instructions,
        parameters=parameters,
    )

    return Task(
        description=description,
        expected_output=(
            "Deliver a brief request_summary (one or two sentences) that restates the "
            "user's ask and notes the action taken. Do not emit JSON, raw tool data, "
            "or any persisted results—Python handles storage separately."
        ),
        agent=agent,
        async_execution=False,
    )
