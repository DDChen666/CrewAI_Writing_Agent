"""Fallback Threads scraper relying on RSSHub public endpoints."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Tuple
from urllib.parse import urlencode

import requests

from .main_scraper import ThreadsTargetError, _detect_target, _normalise_url

_RSSHUB_BASE = "https://rsshub.app/threads"


def _build_rsshub_path(target_url: str) -> Tuple[str, Dict[str, str]]:
    target_type, params = _detect_target(target_url)
    if target_type == "profile":
        handle = params["handle"]
        route = f"user/{handle}"
    elif target_type == "tag_search":
        query = params.get("query") or ""
        if not query:
            raise ThreadsTargetError("Tag searches require a query parameter")
        route = f"tag/{query}"
    else:
        raise ThreadsTargetError(f"Unsupported target for RSSHub: {target_type}")
    return route, {"format": "json"}


def scrape_threads_via_rsshub(
    target_url: str,
    *,
    limit: int = 20,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Fetch Threads data via the public RSSHub service."""

    route, query = _build_rsshub_path(target_url)
    url = f"{_RSSHUB_BASE}/{route}?{urlencode(query)}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    items = payload.get("items", [])[:limit]

    return {
        "platform": "threads",
        "scraper": "rsshub",
        "target": _normalise_url(target_url),
        "fetched_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "post_count": len(items),
        "posts": items,
        "rsshub_route": url,
    }
