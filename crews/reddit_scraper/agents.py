"""Agent definitions for the Reddit scraping crew."""
from __future__ import annotations

from crewai import Agent
from crewai.llm import LLM

from .tools import reddit_api_tool, reddit_subreddit_tool


def build_reddit_scraper_agent() -> Agent:
    """Construct the primary agent responsible for Reddit scraping."""
    llm = LLM(
        model="gemini/gemini-2.5-flash",
        temperature=0.2,
    )

    return Agent(
        role="Reddit Data Acquisition Specialist",
        goal=(
            "Understand natural language requests and translate them into actionable "
            "Reddit Data API calls that return structured results."
        ),
        backstory=(
            "You are an expert Reddit data engineer. You know how to use the official "
            "Reddit Data API and client-credential OAuth flow to pull any resource, "
            "including listings, comments, users and mod tools. You output structured "
            "JSON responses that downstream systems can rely on."
        ),
        llm=llm,
        tools=[reddit_subreddit_tool, reddit_api_tool],
        allow_delegation=False,
        verbose=True,
    )
