"""Primary Threads scraping strategy based on public `threads.net` pages."""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)


class ThreadsTargetError(ValueError):
    """Raised when the provided Threads URL cannot be parsed."""


def _normalise_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or "www.threads.net"
    if netloc.endswith("threads.com"):
        netloc = netloc.replace("threads.com", "threads.net")
    path = parsed.path or "/"
    rebuilt = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    return rebuilt


def _detect_target(url: str) -> Tuple[str, Dict[str, str]]:
    url = _normalise_url(url)
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path.startswith("@"):  # User profile
        return "profile", {"handle": path.lstrip("@")}

    if path.startswith("search"):
        params = parse_qs(parsed.query)
        if params.get("serp_type", [""])[0] == "tags":
            tag_id = params.get("tag_id", [""])[0]
            query = params.get("q", [""])[0]
            return "tag_search", {"tag_id": tag_id, "query": query}
    raise ThreadsTargetError(f"Unsupported Threads URL: {url}")


def _extract_next_data(html: str) -> Dict[str, Any]:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise ThreadsTargetError("Unable to locate __NEXT_DATA__ payload")
    data = json.loads(match.group(1))
    return data


def _collect_profile_threads(data: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    posts: List[Dict[str, Any]] = []
    user_data = (
        data.get("props", {})
        .get("pageProps", {})
        .get("userProfile", {})
        .get("data", {})
        .get("user")
    )
    if not user_data:
        return posts

    threads = user_data.get("threads", {}).get("items", [])
    for item in threads[:limit]:
        thread = item.get("thread", {})
        thread_items = thread.get("thread_items", [])
        if not thread_items:
            continue
        post = thread_items[0].get("post", {})
        attachments: List[Dict[str, Any]] = []
        for media in post.get("media", []) or []:
            media_type = media.get("__typename")
            url = None
            if isinstance(media.get("image_versions2"), dict):
                candidates = media["image_versions2"].get("candidates", [])
                if candidates:
                    url = candidates[0].get("url")
            attachments.append({"type": media_type, "url": url})
        posts.append(
            {
                "id": post.get("id"),
                "code": post.get("code"),
                "created_at": post.get("taken_at"),
                "caption": (post.get("caption") or {}).get("text"),
                "like_count": post.get("like_count"),
                "reply_count": post.get("reply_count"),
                "repost_count": post.get("repost_count"),
                "media": attachments,
                "permalink": post.get("share_info", {}).get("share_url"),
            }
        )
        if len(posts) >= limit:
            break
    return posts


def scrape_threads_via_threadsnet(
    target_url: str,
    *,
    limit: int = 20,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Scrape Threads content by parsing the public `threads.net` HTML."""

    target_type, _ = _detect_target(target_url)
    url = _normalise_url(target_url)

    logger.info("Scraping Threads %s via threads.net HTML", target_type)

    headers = {"User-Agent": _USER_AGENT}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    data = _extract_next_data(response.text)

    if target_type == "profile":
        posts = _collect_profile_threads(data, limit)
    else:
        raise ThreadsTargetError("Tag search pages require the fallback strategy")

    return {
        "platform": "threads",
        "scraper": "threads_net",
        "target": target_url,
        "target_type": target_type,
        "fetched_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "post_count": len(posts),
        "posts": posts,
    }
