"""Task definitions for the Reddit scraping crew."""
from __future__ import annotations

from crewai import Task


def build_reddit_scraping_task(agent) -> Task:
    """Create the main task that interprets user intent."""
    return Task(
        description=(
            "You receive a natural language request that describes what Reddit data "
            "should be fetched. The request to satisfy is: '{{user_request}}'. "
            "Decide which API endpoints or tools to call to fulfil the request. Always "
            "prefer the structured subreddit scraper tool for subreddit listings and "
            "pass a JSON object containing: subreddit, limit, sort, time_filter (only "
            "when sort='top'), comment_depth (0-10 or 'all' to fully expand), skip_media, "
            "and timeout. Interpret 'best' as 'top' and default its time_filter to 'day'; "
            "note this correction in the final request_summary. Requests targeting "
            "profiles should call reddit_api_gateway twice: GET /user/<username>/about and "
            "GET /user/<username>/submitted?limit=...&sort=.... "
            "Use the generic API gateway for any non-listing Reddit Data API call. "
            "Always provide tool arguments as JSON dictionaries, and you may chain "
            "multiple tool calls to satisfy the request. When the user asks for 'all "
            "comments', invoke the subreddit tool with comment_depth='all' so the "
            "scraper expands every thread until no 'more' remain."
        ),
        expected_output=(
            "Deliver a brief request_summary (one or two sentences) that restates the "
            "user's ask and notes the action taken. Do not emit JSON, raw tool data, "
            "or any persisted results—Python handles storage separately."
        ),
        agent=agent,
        async_execution=False,
    )
