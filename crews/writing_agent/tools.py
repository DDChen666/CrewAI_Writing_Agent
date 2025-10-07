"""Specialised tools available to the Writing Agent."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class WritingStyleArgs(BaseModel):
    """Arguments accepted by the writing style helper tools."""

    text: str = Field(
        ..., description="Source text or outline that requires style-specific transformation"
    )
    key_messages: List[str] = Field(
        default_factory=list,
        description="Optional list of key talking points that must be preserved",
    )


class _StyleGuidelineTool(BaseTool):
    """Base class for tools that emit style-specific rewrite guidelines."""

    style_id: str = "generic"
    tone_descriptors: List[str] = []
    structural_tips: List[str] = []
    platform_notes: List[str] = []

    args_schema: Type[BaseModel] = WritingStyleArgs

    def _build_payload(self, text: str, key_messages: List[str]) -> Dict[str, Any]:
        preview_limit = 800
        payload: Dict[str, Any] = {
            "status": "success",
            "tool": self.name,
            "style": self.style_id,
            "tone_descriptors": self.tone_descriptors,
            "structural_tips": self.structural_tips,
            "platform_notes": self.platform_notes,
            "source_text_preview": text[:preview_limit],
            "source_text_truncated": len(text) > preview_limit,
        }
        if key_messages:
            payload["key_messages"] = key_messages
        return payload

    def _run(  # type: ignore[override]
        self,
        text: str,
        key_messages: List[str] | None = None,
    ) -> str:
        payload = self._build_payload(text=text, key_messages=key_messages or [])
        return json.dumps(payload, ensure_ascii=False, indent=2)


class FacebookWriterTool(_StyleGuidelineTool):
    name: str = "facebook_writer"
    description: str = (
        "Provide newsroom-friendly rewrite guidelines optimised for Facebook posts, focusing on "
        "scroll-stopping hooks and concise CTAs."
    )
    style_id: str = "facebook"
    tone_descriptors: List[str] = ["approachable", "community-focused", "credibility-first"]
    structural_tips: List[str] = [
        "Lead with a single-sentence hook that frames the payoff or tension",
        "Use short paragraphs and emoji sparingly to highlight key stats or promises",
        "Close with a direct CTA that matches a conversion or engagement goal",
    ]
    platform_notes: List[str] = [
        "Optimise for mobile users who skim quickly",
        "Highlight social proof or community impact when available",
        "Respect Facebook's preference for plain-text CTAs over hashtag heavy endings",
    ]


class XWriterTool(_StyleGuidelineTool):
    name: str = "x_writer"
    description: str = (
        "Return rewrite guidance for X/Twitter threads, emphasising punchy cadence and shareable insights."
    )
    style_id: str = "x"
    tone_descriptors: List[str] = ["succinct", "opinionated", "data-backed"]
    structural_tips: List[str] = [
        "Craft a lead tweet with a bold claim or surprising stat",
        "Break supporting points into a numbered micro-thread",
        "End with a question or actionable takeaway to encourage replies",
    ]
    platform_notes: List[str] = [
        "Keep each tweet under 240 characters while preserving clarity",
        "Use at most two relevant hashtags to retain reach without spam",
        "Tag influential accounts only when the reference is substantive",
    ]


class ThreadWriterTool(_StyleGuidelineTool):
    name: str = "thread_writer"
    description: str = (
        "Emit long-form, forum-ready rewrite guidance suited for platforms like Threads or LinkedIn articles."
    )
    style_id: str = "thread"
    tone_descriptors: List[str] = ["reflective", "insightful", "mentor-like"]
    structural_tips: List[str] = [
        "Open with a narrative or question that mirrors the audience's pain point",
        "Alternate between insight paragraphs and bullet lists for readability",
        "Wrap with a reflective close that reinforces brand authority",
    ]
    platform_notes: List[str] = [
        "Encourage saves/shares by highlighting frameworks or step-by-step guidance",
        "Reference credible data sources and attribution links",
        "Invite dialogue by prompting readers to share their playbooks or questions",
    ]


facebook_writer_tool = FacebookWriterTool()
x_writer_tool = XWriterTool()
thread_writer_tool = ThreadWriterTool()

__all__ = [
    "facebook_writer_tool",
    "x_writer_tool",
    "thread_writer_tool",
]
