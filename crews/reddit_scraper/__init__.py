"""Reddit scraping crew package."""
from __future__ import annotations

import os

os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_DISABLE_ANALYTICS", "true")
os.environ.setdefault("CREWAI_ENABLE_TELEMETRY", "false")

from .crew import RedditScraperCrew

__all__ = ["RedditScraperCrew"]
