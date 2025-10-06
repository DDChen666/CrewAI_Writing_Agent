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
            "prefer the structured subreddit scraper tool for listing style requests. "
            "Use the generic API gateway only when the request requires actions beyond "
            "listings (for example moderators, user profiles, search, or metadata). "
            "Combine multiple calls if necessary. When calling a tool you MUST provide "
            "a valid JSON dictionary (not a string) containing the required arguments."
        ),
        expected_output=(
            "Return a single JSON object. Include a 'request_summary' field describing "
            "the interpreted ask, and a 'results' field containing either a single tool "
            "response or an array of responses if multiple calls are made. Ensure the "
            "JSON is valid and contains only data with no commentary."
        ),
        agent=agent,
        async_execution=False,
    )
