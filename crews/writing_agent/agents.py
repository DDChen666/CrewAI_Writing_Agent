"""Agent definitions for the Writing Agent crew."""
from __future__ import annotations

from typing import Dict

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


def _build_llm(temperature: float) -> LLM:
    return LLM(
        model="gemini/gemini-2.5-flash",
        temperature=temperature,
    )


def build_editor_in_chief_agent() -> Agent:
    """Agent that digests briefs and crafts the strategic blueprint."""

    return Agent(
        role="Editorial Strategy Director",
        goal=(
            "Translate prioritized_topic_briefs into a strategic blueprint that encodes STEPPS triggers, "
            "audience psychology and verifiable proof points so downstream writers can execute flawlessly."
        ),
        backstory=(
            "You are a newsroom editor trained in behavioural science and viral growth systems. You map "
            "audience tensions to brand promises, insist on dataset-backed evidence and de-risk topics before "
            "they reach production. Your work references the DR_爆文生產系統性方法研究 playbook."
        ),
        llm=_build_llm(temperature=0.2),
        tools=[content_explorer_tool],
        allow_delegation=False,
        verbose=True,
    )


def build_hook_architect_agent() -> Agent:
    """Agent that transforms the blueprint into scroll-stopping hooks."""

    return Agent(
        role="Hook and Narrative Architect",
        goal=(
            "Design multi-platform hooks and outline beats that combine STEPPS with advanced triggers such as "
            "信息差、FOMO 和預期心理, ensuring each idea ladders back to the strategic blueprint."
        ),
        backstory=(
            "You specialise in viral copy systems. You remix the blueprint into specific hooks, cross-channel "
            "story arcs and CTA ladders. You are fluent in the DR viral framework and know how to keep tokens "
            "lean by working from distilled insights."
        ),
        llm=_build_llm(temperature=0.35),
        tools=[
            content_explorer_tool,
            facebook_writer_tool,
            x_writer_tool,
            thread_writer_tool,
        ],
        allow_delegation=False,
        verbose=True,
    )


def build_master_writer_agent() -> Agent:
    """Agent that crafts production-ready long/short-form rewrites."""

    return Agent(
        role="Lead Conversion Writer",
        goal=(
            "Craft channel-ready drafts that activate the agreed trigger stack, protect factual integrity and "
            "package the story arc into irresistible copy tailored to each platform."
        ),
        backstory=(
            "You are the closer. You turn blueprints into polished drafts while citing dataset evidence, "
            "balancing emotional payoff with practical value. You maintain the brand promise '更智慧、更省力、更美好'."
        ),
        llm=_build_llm(temperature=0.45),
        tools=[
            content_explorer_tool,
            facebook_writer_tool,
            x_writer_tool,
            thread_writer_tool,
        ],
        allow_delegation=False,
        verbose=True,
    )


def build_editorial_guardian_agent() -> Agent:
    """Agent that performs final QA and risk mitigation."""

    return Agent(
        role="Editorial Guardian",
        goal=(
            "Stress-test the draft against brand guardrails, ensure claims are traceable to dataset_id and "
            "append a concise QA report with improvement notes."
        ),
        backstory=(
            "You audit final outputs for factuality, compliance and persuasive completeness. You cross-check "
            "the trigger stack, verify citations and flag mitigation steps."
        ),
        llm=_build_llm(temperature=0.15),
        tools=[content_explorer_tool],
        allow_delegation=False,
        verbose=True,
    )


def build_writing_team() -> Dict[str, Agent]:
    """Return the full team of agents collaborating on the writing workflow."""

    return {
        "editor_in_chief": build_editor_in_chief_agent(),
        "hook_architect": build_hook_architect_agent(),
        "master_writer": build_master_writer_agent(),
        "editorial_guardian": build_editorial_guardian_agent(),
    }


def build_writing_agent() -> Agent:
    """Backward compatible helper returning the master writer agent."""

    return build_master_writer_agent()


__all__ = [
    "build_editor_in_chief_agent",
    "build_hook_architect_agent",
    "build_master_writer_agent",
    "build_editorial_guardian_agent",
    "build_writing_team",
    "build_writing_agent",
]
