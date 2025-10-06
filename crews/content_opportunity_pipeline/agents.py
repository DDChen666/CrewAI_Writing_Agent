"""Agent definitions for the Content Opportunity Pipeline."""
from __future__ import annotations

from crewai import Agent
from crewai.llm import LLM

from .tools import (
    reddit_dataset_export_tool,
    reddit_dataset_filter_tool,
    reddit_dataset_lookup_tool,
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


def build_trend_analysis_agent() -> Agent:
    """Create the Trend Analysis Agent responsible for clustering and momentum scoring."""

    llm = LLM(
        model="gemini/gemini-2.0-flash-thinking",
        temperature=0.2,
    )

    return Agent(
        role="Trend Analysis Agent",
        goal=(
            "Digest Cleaned_Content_Stream payloads and produce an Identified_Trends_Report "
            "summarising potential topic clusters, their momentum, sentiment profile and KOLs."
        ),
        backstory=(
            "You are a quantitative trend spotter specialising in emerging Reddit discourse. "
            "You excel at semantic clustering, temporal analysis and identifying early signals. "
            "Always transform observations into structured data that conforms to the "
            "IdentifiedTrendsReport schema. Use the dataset lookup tool whenever you need "
            "to inspect specific posts referenced by post_id."
        ),
        llm=llm,
        tools=[reddit_dataset_lookup_tool],
        allow_delegation=False,
        verbose=True,
    )


def build_brand_alignment_agent() -> Agent:
    """Create the Brand Alignment Agent responsible for scoring opportunities."""

    llm = LLM(
        model="gemini/gemini-2.0-flash",
        temperature=0.15,
    )

    return Agent(
        role="Brand Alignment Agent",
        goal=(
            "Evaluate trend clusters against the Brand Core Knowledge Base and output a "
            "Scored_And_Filtered_Opportunities list ranked by relevance, ICP fit and risk."
        ),
        backstory=(
            "You are the strategic gatekeeper for JustKa AI. You absorb the brand knowledge "
            "base, interpret relevance through the lens of ICP, funnel stage and risk, and "
            "articulate your assessment within the ScoredAndFilteredOpportunities schema. "
            "Use the dataset lookup tool to pull representative Reddit posts for deeper "
            "audience analysis before finalising scores."
        ),
        llm=llm,
        tools=[reddit_dataset_lookup_tool],
        allow_delegation=False,
        verbose=True,
    )


def build_topic_curator_agent() -> Agent:
    """Create the Topic Curator Agent that packages final production briefs."""

    llm = LLM(
        model="gemini/gemini-2.0-pro",
        temperature=0.35,
    )

    return Agent(
        role="Topic Curator Agent",
        goal=(
            "Select the highest leverage opportunities and turn them into Prioritized_Topic_Brief "
            "packages with compelling editorial angles."
        ),
        backstory=(
            "You operate like a chief editor who understands growth marketing. You balance "
            "brand fit, funnel intent and trend momentum to select 1-3 standout opportunities. "
            "For each, craft 3-5 angles and capture supporting insights exactly as required by "
            "the PrioritizedTopicBrief schema."
        ),
        llm=llm,
        tools=[],
        allow_delegation=False,
        verbose=True,
    )
