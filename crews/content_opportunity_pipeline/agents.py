"""Agent definitions for the Content Opportunity Pipeline."""
from __future__ import annotations

from crewai import Agent
from crewai.llm import LLM

from .tools import (
    reddit_dataset_export_tool,
    reddit_dataset_filter_tool,
    reddit_scrape_loader_tool,
    reddit_scrape_locator_tool,
)


def build_data_triage_agent() -> Agent:
    """Create the Data Triage Agent responsible for Reddit data selection."""

    llm = LLM(
        model="gemini/gemini-2.5-flash",
        temperature=0.1,
    )

    return Agent(
        role="Data Triage Agent",
        goal=(
            "Quickly interpret operator prompts, locate the correct raw Reddit scrape files, "
            "and emit a normalised, de-duplicated Cleaned_Content_Stream focused on the "
            "metrics the operator cares about."
        ),
        backstory=(
            "You are the pipeline's first responder. Your job is to shield downstream analysts "
            "from noisy or irrelevant submissions. You understand how Reddit scrape JSON files "
            "are structured (platform, subreddit, items, statistics) and you always use the "
            "available tools to inspect file inventories, load posts, filter by engagement "
            "metrics, and export a consistent payload. You never attempt to read raw JSON "
            "directly – every transformation goes through the registered tools."
        ),
        llm=llm,
        tools=[
            reddit_scrape_locator_tool,
            reddit_scrape_loader_tool,
            reddit_dataset_filter_tool,
            reddit_dataset_export_tool,
        ],
        allow_delegation=False,
        verbose=True,
    )
