"""Schemas for structured outputs from the Writing Agent."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


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


__all__ = ["RewriteVariant", "WritingAgentOutput"]
