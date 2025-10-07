"""Agent definitions for the Writing Agent crew."""
from __future__ import annotations

from crewai import Agent
from crewai.llm import LLM

from ..common import ensure_gemini_rate_limit
from ..content_opportunity_pipeline.tools import content_explorer_tool

from .tools import (
    facebook_writer_tool,
    thread_writer_tool,
    x_writer_tool,
)


ensure_gemini_rate_limit()


def build_writing_agent() -> Agent:
    """Create the Writing Agent responsible for platform-specific rewrites."""

    llm = LLM(
        model="gemini/gemini-2.5-flash",
        temperature=0.35,
    )

    return Agent(
        role="Content Writing Agent",
        goal=(
            "Transform validated opportunities into channel-ready copy while preserving brand promises, "
            "data fidelity and risk guardrails."
        ),
        backstory=(
            "You are the finishing specialist for the Content Opportunity Pipeline. You ingest structured "
            "trend, opportunity and brief artifacts, inspect underpinning Reddit posts via dataset lookup "
            "tools, and craft production-ready drafts tuned to the requested platform style. You handle "
            "ambiguity by clarifying assumptions, ensure factual claims remain traceable to the dataset_id, "
            "and document editorial notes for downstream reviewers."
        ),
        llm=llm,
        tools=[
            content_explorer_tool,
            facebook_writer_tool,
            x_writer_tool,
            thread_writer_tool,
        ],
        allow_delegation=False,
        verbose=True,
    )


__all__ = ["build_writing_agent"]
