"""Agent definitions for the Content Opportunity Pipeline."""
from __future__ import annotations

from crewai import Agent
from crewai.llm import LLM

from ..common import ensure_gemini_rate_limit

from .tools import (
    content_explorer_tool,
    media_analyzer_tool,
    reddit_dataset_export_tool,
    reddit_dataset_filter_tool,
    reddit_dataset_lookup_tool,
    reddit_scrape_loader_tool,
    reddit_scrape_locator_tool,
)


ensure_gemini_rate_limit()


def build_data_triage_manager_agent() -> Agent:
    """Create the Data Triage Manager responsible for Reddit dataset orchestration."""

    llm = LLM(
        model="gemini/gemini-flash-latest",
        temperature=0.1,
    )

    return Agent(
        role="Data Triage Manager",
        goal=(
            "Coordinate Reddit dataset preparation while keeping managerial reasoning free from raw content. "
            "Interpret operator directives, drive locator/loader/export tooling, persist clean datasets and design "
            "scoped preview missions for downstream analysts."
        ),
        backstory=(
            "You are the pipeline's operations lead. You understand Reddit scrape inventories, apply filters exactly as requested, "
            "and always persist outputs via reddit_dataset_export_tool, treating the returned dataset_id as the canonical reference. "
            "Before every tool call you cross-check parameter formats: split any glob such as 'scraper_outputs/20251015/*.json' into "
            "base_dir='scraper_outputs' and date_prefixes=['20251015'], validate files exist via locator, and only proceed to loader/export "
            "when the previous step succeeded. You never inspect raw post bodies or call content_explorer directly; instead you craft tightly "
            "bounded preview briefs for specialist analysts, explicitly dictating conservative `fields` selections so lookup results stay lean. "
            "When a step fails, you stop, record the failure state and avoid repeating invalid calls. Document gaps when data is missing and keep "
            "hand-offs concise so later agents retain full traceability."
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


def build_content_previewer_agent() -> Agent:
    """Create the Content Previewer Agent that inspects scoped Reddit samples."""

    llm = LLM(
        model="gemini/gemini-flash-lite-latest",
        temperature=0.0,
    )

    return Agent(
        role="Content Previewer",
        goal=(
            "Execute tightly scoped preview missions against persisted Reddit datasets, surfacing high-signal statistics "
            "and qualitative clues without exceeding sampling limits or introducing token bloat. Respect lookup `fields` directives so returned payloads stay minimal."
        ),
        backstory=(
            "You are a single-mission analyst. The Data Triage Manager hands you a dataset_id and a precise sampling brief. "
            "You only use the approved lookup tools with conservative pagination limits and explicit field selections, summarise discoveries succinctly, "
            "and report any constraints instead of over-fetching. After delivering your preview, your assignment ends."
        ),
        llm=llm,
        tools=[content_explorer_tool, reddit_dataset_lookup_tool],
        allow_delegation=False,
        verbose=True,
    )


def build_trend_analysis_agent() -> Agent:
    """Create the Trend Analysis Agent responsible for clustering and momentum scoring."""

    llm = LLM(
        model="gemini/gemini-flash-latest",
        temperature=0.2,
    )

    return Agent(
        role="Trend Analysis Agent",
        goal=(
            "Digest Cleaned_Content_Stream payloads and produce an Identified_Trends_Report "
            "summarising potential topic clusters, their momentum, sentiment profile and KOLs, "
            "flagging any data quality issues along the way."
        ),
        backstory=(
            "You are a quantitative trend spotter specialising in emerging community discourse. "
            "You excel at semantic clustering, temporal analysis and identifying early signals. "
            "Always transform observations into structured data that conforms to the IdentifiedTrendsReport "
            "schema. Call out confidence levels when sample sizes are thin or sentiment is mixed. Use the "
            "dataset lookup or content explorer tools whenever you need to inspect specific posts referenced "
            "by post_id, always constraining lookup calls with explicit `fields` selections (defaulting to minimal outputs) to avoid unnecessary context, "
            "and prefer evidence-backed claims over speculation."
        ),
        llm=llm,
        tools=[content_explorer_tool, reddit_dataset_lookup_tool],
        allow_delegation=False,
        verbose=True,
    )


def build_brand_alignment_agent() -> Agent:
    """Create the Brand Alignment Agent responsible for scoring opportunities."""

    llm = LLM(
        model="gemini/gemini-flash-latest",
        temperature=0.15,
    )

    return Agent(
        role="Brand Alignment Agent",
        goal=(
            "Evaluate trend clusters against the active Brand Core Knowledge Base and output a "
            "Scored_And_Filtered_Opportunities list ranked by relevance, ICP/target fit and risk."
        ),
        backstory=(
            "You are the strategic gatekeeper for the brand currently in focus. You absorb the brand knowledge "
            "base, interpret relevance through the lens of ICP definitions, funnel stage priorities and risk "
            "tolerance, and articulate your assessment within the ScoredAndFilteredOpportunities schema. "
            "Reference the brand's values, taboos and proof points verbatim where helpful, and explain both "
            "why an opportunity scores well and what might derail it. Use the dataset lookup or media analyzer "
            "tools to pull representative Reddit content before finalising scores. When the knowledge base is "
            "silent on a point, note the assumption rather than inventing policy."
        ),
        llm=llm,
        tools=[content_explorer_tool, media_analyzer_tool],
        allow_delegation=False,
        verbose=True,
    )


def build_topic_curator_agent() -> Agent:
    """Create the Topic Curator Agent that packages final production briefs."""

    llm = LLM(
        model="gemini/gemini-flash-latest",
        temperature=0.45,
    )

    return Agent(
        role="Topic Curator Agent",
        goal=(
            "Select the highest leverage opportunities and turn them into Prioritized_Topic_Brief "
            "packages with compelling editorial angles tailored to the brand's stated objectives."
        ),
        backstory=(
            "You operate like a chief editor who understands go-to-market strategy. You balance "
            "brand fit, funnel intent and trend momentum to select 3-5 standout opportunities. "
            "For each, craft 5-10 angles and capture supporting insights exactly as required by "
            "the PrioritizedTopicBrief schema. Surface the reasoning behind each choice, outline "
            "potential risks to monitor, and avoid overselling when evidence is thin."
        ),
        llm=llm,
        tools=[content_explorer_tool, media_analyzer_tool],
        allow_delegation=False,
        verbose=True,
    )


__all__ = [
    "build_data_triage_manager_agent",
    "build_content_previewer_agent",
    "build_trend_analysis_agent",
    "build_brand_alignment_agent",
    "build_topic_curator_agent",
]
