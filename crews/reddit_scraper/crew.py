"""Crew entry-point for the Reddit scraping workflow."""
from __future__ import annotations

from crewai import Crew

from .agents import build_reddit_scraper_agent
from .tasks import build_reddit_scraping_task


class RedditScraperCrew:
    """High-level orchestrator that exposes a `run` helper."""

    def __init__(self) -> None:
        agent = build_reddit_scraper_agent()
        task = build_reddit_scraping_task(agent)
        self.crew = Crew(agents=[agent], tasks=[task], verbose=True)

    def run(self, user_request: str) -> str:
        """Execute the crew with the supplied natural language request."""
        result = self.crew.kickoff(inputs={"user_request": user_request})
        return result


__all__ = ["RedditScraperCrew"]
