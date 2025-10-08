"""Schemas for structured outputs from the Writing Agent."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ViralFrameworkApplication(BaseModel):
    """How a persuasion or virality framework is applied in the piece."""

    framework: str = Field(
        ..., description="Name of the persuasion/virality framework being invoked"
    )
    objective: str = Field(
        ..., description="The communication goal this framework reinforces"
    )
    execution: str = Field(
        ..., description="Concrete copy or structural choice that applies the framework"
    )


class EditorialRisk(BaseModel):
    """Potential brand, factual or compliance risk surfaced by reviewers."""

    risk: str = Field(..., description="Short description of the potential risk")
    severity: str = Field(
        ..., description="Qualitative severity (e.g. low/medium/high) with justification"
    )
    mitigation_plan: str = Field(
        ..., description="Recommended mitigation or follow-up action"
    )


class StrategicBlueprint(BaseModel):
    """Upstream briefing that grounds the eventual rewrite."""

    selected_brief_title: str = Field(
        ..., description="Title or topic of the prioritized brief powering this rewrite"
    )
    audience_insight: str = Field(
        ..., description="Succinct description of the audience tension or desire"
    )
    brand_promise: str = Field(
        ..., description="How the brand resolves the tension in line with its positioning"
    )
    key_data_points: List[str] = Field(
        default_factory=list,
        description="Quantitative or qualitative proof points lifted from the dataset",
    )
    psychological_triggers: List[str] = Field(
        default_factory=list,
        description="List of STEPPS/advanced triggers intentionally activated",
    )
    story_arc: List[str] = Field(
        default_factory=list,
        description="Ordered outline beats that will structure the narrative",
    )
    framework_applications: List[ViralFrameworkApplication] = Field(
        default_factory=list,
        description="How specific persuasion frameworks will materialise inside the copy",
    )
    editorial_risks: List[EditorialRisk] = Field(
        default_factory=list,
        description="Known risks the downstream writer and editor must monitor",
    )


class HookConcept(BaseModel):
    """A platform-ready hook or angle derived from the blueprint."""

    platform: str = Field(
        ..., description="Channel or format the hook is optimised for"
    )
    hook: str = Field(..., description="Scroll-stopping hook, headline or opening line")
    supporting_promise: str = Field(
        ..., description="What payoff the hook promises to the audience"
    )
    trigger_stack: List[str] = Field(
        default_factory=list,
        description="Psychological triggers blended inside this hook",
    )
    validation_notes: Optional[str] = Field(
        None,
        description="Why this hook should resonate, referencing dataset observations",
    )


class QualityReview(BaseModel):
    """Final self-check applied to the finished rewrite."""

    compliance_checks: List[str] = Field(
        default_factory=list,
        description="Confirmed guardrails (facts verified, brand taboos avoided)",
    )
    improvement_notes: List[str] = Field(
        default_factory=list,
        description="Actionable follow-ups for human editors or distribution teams",
    )
    confidence_rating: str = Field(
        ..., description="Overall confidence statement with rationale"
    )


class RewriteVariant(BaseModel):
    """Represents a single platform-specific rewrite of the brief."""

    platform: str = Field(..., description="Target platform or channel for the rewrite")
    tone: Optional[str] = Field(
        None, description="Optional tone or stylistic direction applied to this variant"
    )
    headline: Optional[str] = Field(
        None, description="Optional headline or leading hook for the content"
    )
    body: str = Field(..., description="Main body copy for the platform-specific rewrite")
    call_to_action: Optional[str] = Field(
        None, description="Suggested call-to-action tailored to the platform"
    )
    supporting_points: List[str] = Field(
        default_factory=list,
        description="Key points or proof elements carried into this rewrite",
    )
    references: List[str] = Field(
        default_factory=list,
        description="Links or dataset references used while drafting this rewrite",
    )


class WritingAgentOutput(BaseModel):
    """Top level schema produced by the Writing Agent."""

    source_pipeline_file: str = Field(
        ..., description="Path to the content opportunity pipeline output that seeded this rewrite"
    )
    dataset_id: Optional[str] = Field(
        None,
        description="Dataset identifier used to retrieve source Reddit content when applicable",
    )
    prompt_summary: Optional[str] = Field(
        None,
        description="Short description of how the user request was interpreted for this rewrite",
    )
    rewrites: List[RewriteVariant] = Field(
        ..., description="Collection of channel-specific rewrites produced by the agent"
    )
    editorial_notes: List[str] = Field(
        default_factory=list,
        description="Additional notes or considerations for downstream editorial teams",
    )
    strategic_blueprint: Optional[StrategicBlueprint] = Field(
        None,
        description="Upstream strategic plan that guided the draft",
    )
    hook_concepts: List[HookConcept] = Field(
        default_factory=list,
        description="Collection of shortlisted hooks or openings for each platform",
    )
    quality_review: Optional[QualityReview] = Field(
        None,
        description="Final QA assessment appended by the editorial guardian",
    )


__all__ = [
    "ViralFrameworkApplication",
    "EditorialRisk",
    "StrategicBlueprint",
    "HookConcept",
    "QualityReview",
    "RewriteVariant",
    "WritingAgentOutput",
]
