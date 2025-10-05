"""Fallback Facebook scraper implementation using RSSHub public routes."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode

import requests

from .main_scraper import _extract_target

_RSSHUB_BASE = "https://rsshub.app/facebook"


def _build_rsshub_route(target_url: str) -> Tuple[str, Dict[str, str]]:
    target_type, identifier = _extract_target(target_url)
    if target_type == "group":
        route = f"group/{identifier}"
    else:
        route = f"page/{identifier}"
    query = {"format": "json"}
    return route, query


def _transform_item(item: Dict[str, Any]) -> Dict[str, Any]:
    media: List[Dict[str, Any]] = []
    if enclosure := item.get("enclosure"):
        media.append({"type": enclosure.get("type"), "url": enclosure.get("url")})
    return {
        "title": item.get("title"),
        "summary": item.get("description"),
        "link": item.get("link"),
        "guid": item.get("guid"),
        "published": item.get("pubDate"),
        "media": media,
    }


def scrape_facebook_via_rsshub(
    target_url: str,
    *,
    limit: int = 20,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Fallback strategy relying on the public RSSHub instance."""

    route, query = _build_rsshub_route(target_url)
    url = f"{_RSSHUB_BASE}/{route}?{urlencode(query)}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    items = payload.get("items", [])[:limit]
    posts = [_transform_item(item) for item in items]

    return {
        "platform": "facebook",
        "scraper": "rsshub",
        "target": target_url,
        "fetched_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "post_count": len(posts),
        "posts": posts,
        "rsshub_route": url,
    }
