"""Crew entry-point for the Reddit scraping workflow."""
from __future__ import annotations

from typing import Any, Dict, Optional

from crewai import Crew

from cli_common import DirectiveBlock

from .agents import build_reddit_scraper_agent
from .tasks import build_reddit_scraping_task


class RedditScraperCrew:
    """High-level orchestrator that exposes a `run` helper."""

    def __init__(self) -> None:
        self.crew: Optional[Crew] = None

    @staticmethod
    def _safe_block(directives: Optional[Dict[str, DirectiveBlock]]) -> DirectiveBlock:
        if directives is None:
            return DirectiveBlock(instructions="", parameters={})

        global_block = directives.get("global")
        scraper_block = directives.get("scraper") or directives.get("reddit") or directives.get("fetch")

        instructions_parts = []
        parameters: Dict[str, Any] = {}

        if global_block is not None:
            if global_block.instructions.strip():
                instructions_parts.append(global_block.instructions.strip())
            parameters.update(global_block.parameters)
        if scraper_block is not None:
            if scraper_block.instructions.strip():
                instructions_parts.append(scraper_block.instructions.strip())
            parameters.update(scraper_block.parameters)

        merged_instructions = "\n\n".join(instructions_parts).strip()
        return DirectiveBlock(instructions=merged_instructions, parameters=parameters)

    def _build_crew(self, directives: Optional[Dict[str, DirectiveBlock]]) -> Crew:
        block = self._safe_block(directives)
        agent = build_reddit_scraper_agent()
        task = build_reddit_scraping_task(
            agent,
            instructions=block.instructions,
            parameters=block.parameters,
        )
        crew = Crew(agents=[agent], tasks=[task], verbose=True)
        return crew

    def run(self, user_request: str, directives: Optional[Dict[str, DirectiveBlock]] = None) -> str:
        """Execute the crew with the supplied natural language request."""
        crew = self._build_crew(directives)
        self.crew = crew
        block = self._safe_block(directives)
        result = crew.kickoff(inputs={
            "user_request": user_request,
            "global_operator_notes": block.instructions,
        })
        return result


__all__ = ["RedditScraperCrew"]
