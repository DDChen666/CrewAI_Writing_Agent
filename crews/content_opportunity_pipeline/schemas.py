"""Pydantic schemas for structured outputs within the Content Opportunity Pipeline."""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class TrendCluster(BaseModel):
    """Representation of a clustered Reddit discussion trend."""

    cluster_id: str = Field(..., description="Stable identifier for the topic cluster")
    core_keywords: List[str] = Field(..., description="Representative keywords or n-grams that define the cluster")
    representative_post_ids: List[str] = Field(
        ..., description="Post identifiers that exemplify the topic cluster"
    )
    sentiment_label: str = Field(
        ..., description="Sentiment classification such as Positive, Negative, Neutral or Controversial"
    )
    trend_velocity: float = Field(
        ..., description="First derivative of conversation volume – how fast interest is growing"
    )
    trend_acceleration: float = Field(
        ..., description="Second derivative of conversation volume to surface emerging breakouts"
    )
    key_opinion_leaders: List[str] = Field(
        default_factory=list, description="High influence authors driving the conversation"
    )
    lifecycle_stage: str = Field(
        ..., description="Lifecycle stage label (Nascent, Emerging, Mature, Decaying)"
    )


class IdentifiedTrendsReport(BaseModel):
    """Report emitted by the Trend Analysis Agent."""

    dataset_id: str = Field(..., description="Reference to the Cleaned_Content_Stream dataset backing the clusters")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when the report was assembled"
    )
    clusters: List[TrendCluster] = Field(..., description="Collection of identified topic clusters")


class ScoredOpportunity(BaseModel):
    """Topic opportunity annotated by the Brand Alignment Agent."""

    cluster_id: str = Field(..., description="Identifier of the originating trend cluster")
    core_keywords: List[str] = Field(..., description="Representative keywords from the originating cluster")
    representative_post_ids: List[str] = Field(..., description="Anchoring posts for context retrieval")
    sentiment_label: str = Field(..., description="Sentiment inherited from the trend analysis stage")
    trend_velocity: float = Field(..., description="Velocity value inherited from the trend analysis stage")
    trend_acceleration: float = Field(..., description="Acceleration value inherited from the trend analysis stage")
    key_opinion_leaders: List[str] = Field(
        default_factory=list, description="Influential voices in the conversation"
    )
    lifecycle_stage: str = Field(..., description="Lifecycle stage inherited from the trend analysis stage")
    relevance_score: float = Field(
        ..., description="Alignment score between the topic and the brand's core domains"
    )
    audience_alignment_score: float = Field(
        ..., description="Fit with the ideal customer persona derived from participant analysis"
    )
    funnel_stage: str = Field(..., description="TOFU/MOFU/BOFU stage placement for the opportunity")
    risk_level: str = Field(..., description="Qualitative risk rating such as Low, Medium, High")


class ScoredAndFilteredOpportunities(BaseModel):
    """Sorted shortlist of opportunities ready for editorial review."""

    source_report_id: str = Field(..., description="Identifier for the originating trend report")
    dataset_id: str = Field(..., description="Dataset reference so downstream agents can fetch raw posts")
    opportunities: List[ScoredOpportunity] = Field(
        ..., description="Opportunities ordered by brand relevance and strategic value"
    )


class PrioritizedTopicBriefEntry(BaseModel):
    """Final packaged brief ready for production planning."""

    topic_title: str = Field(..., description="Human friendly headline for the content opportunity")
    recommended_angles: List[str] = Field(
        ..., description="3-5 distinct angles tailored to the brand voice"
    )
    target_funnel_stage: str = Field(..., description="Selected funnel stage focus for the content piece")
    key_insights: List[str] = Field(
        ..., description="Supporting analytical insights such as sentiment, KOLs or statistics"
    )
    reference_links: List[str] = Field(
        default_factory=list, description="Links to representative Reddit discussions or external sources"
    )
    strategic_priority_score: float = Field(
        ..., description="Composite prioritisation score balancing momentum, fit and urgency"
    )


class PrioritizedTopicBrief(BaseModel):
    """Top level structure produced by the Topic Curator Agent."""

    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when the brief was generated"
    )
    source_opportunity_reference: str = Field(
        ..., description="Identifier for the scored opportunity list powering this brief"
    )
    selected_topics: List[PrioritizedTopicBriefEntry] = Field(
        ..., description="Ranked list of topics approved for immediate production"
    )
