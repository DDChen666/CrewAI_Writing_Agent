"""Primary Facebook scraping strategy using `facebook-scraper`.

The implementation focuses on public pages and groups that do not require
authentication. We rely on the `facebook_scraper` library, which performs
plain HTTP requests without browser automation.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import re
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_POSTS_PER_PAGE = 10


class FacebookTargetError(ValueError):
    """Raised when the provided Facebook target URL cannot be parsed."""


def _extract_target(url: str) -> Tuple[str, str]:
    """Return (target_type, identifier) extracted from a Facebook URL."""

    parsed = urlparse(url)
    if not parsed.netloc:
        raise FacebookTargetError("A full Facebook URL is required")

    path = parsed.path.strip("/")
    if not path:
        raise FacebookTargetError(f"Could not derive a target from {url}")

    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        raise FacebookTargetError(f"Could not derive a target from {url}")

    if segments[0] == "groups":
        if len(segments) < 2:
            raise FacebookTargetError("Group URL is missing an identifier")
        return ("group", segments[1])

    # Remove potential trailing fragments such as "posts" or "videos".
    if segments[-1] in {"posts", "videos", "photos"} and len(segments) > 1:
        segments = segments[:-1]

    slug = segments[-1]
    slug = re.sub(r"[?&].*", "", slug)
    if not slug:
        raise FacebookTargetError(f"Unable to determine page slug from {url}")

    return ("page", slug)


def _serialise_comment(comment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "comment_id": comment.get("comment_id"),
        "comment_url": comment.get("comment_url"),
        "commenter_name": comment.get("commenter_name"),
        "commenter_url": comment.get("commenter_url"),
        "text": comment.get("comment_text"),
        "time": comment.get("comment_time").isoformat() if comment.get("comment_time") else None,
        "replies": [
            {
                "comment_id": reply.get("comment_id"),
                "comment_url": reply.get("comment_url"),
                "commenter_name": reply.get("commenter_name"),
                "commenter_url": reply.get("commenter_url"),
                "text": reply.get("comment_text"),
                "time": reply.get("comment_time").isoformat() if reply.get("comment_time") else None,
            }
            for reply in comment.get("replies", [])
        ],
    }


def _serialise_post(raw_post: Dict[str, Any]) -> Dict[str, Any]:
    media: List[Dict[str, Any]] = []
    if raw_post.get("image"):
        media.append({"type": "image", "url": raw_post.get("image")})
    for image in raw_post.get("images", []) or []:
        media.append({"type": "image", "url": image})
    if raw_post.get("video"):
        media.append({"type": "video", "url": raw_post.get("video")})
    if raw_post.get("video_thumbnail"):
        media.append({"type": "video_thumbnail", "url": raw_post.get("video_thumbnail")})

    comments_source: Iterable[Dict[str, Any]] = raw_post.get("comments_full") or []
    comments = [_serialise_comment(comment) for comment in comments_source]

    return {
        "post_id": raw_post.get("post_id"),
        "post_url": raw_post.get("post_url"),
        "text": raw_post.get("post_text"),
        "time": raw_post.get("time").isoformat() if raw_post.get("time") else None,
        "user_id": raw_post.get("user_id"),
        "user_url": raw_post.get("user_url"),
        "username": raw_post.get("username"),
        "reactions": raw_post.get("reaction_count"),
        "comments": comments,
        "comments_count": raw_post.get("comments"),
        "shares": raw_post.get("shares"),
        "media": media,
        "is_live": raw_post.get("is_live"),
        "fact_check": raw_post.get("factcheck"),
    }


def scrape_facebook_via_facebook_scraper(
    target_url: str,
    *,
    limit: int = 20,
    fetch_comments: bool = True,
    fetch_media: bool = True,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Scrape a Facebook public page or group using `facebook_scraper`.

    Parameters
    ----------
    target_url:
        Full Facebook URL for a public page or group.
    limit:
        Maximum number of posts to fetch.
    fetch_comments:
        Whether to request comment threads.
    fetch_media:
        Whether to include media URLs in the output.
    timeout:
        Network timeout in seconds applied to the underlying HTTP requests.
    """

    target_type, identifier = _extract_target(target_url)
    pages = max(1, math.ceil(limit / _POSTS_PER_PAGE))

    options = {
        "comments": fetch_comments,
        "reactions": True,
        "posts_per_page": _POSTS_PER_PAGE,
        "allow_extra_requests": fetch_media,
    }

    logger.info("Scraping Facebook %s '%s' via facebook-scraper", target_type, identifier)

    posts: List[Dict[str, Any]] = []
    fetch_kwargs: Dict[str, Any]
    if target_type == "group":
        fetch_kwargs = {"group": identifier}
    else:
        fetch_kwargs = {"page": identifier}

    from facebook_scraper import get_posts  # type: ignore[import]

    for index, post in enumerate(
        get_posts(
            pages=pages,
            options=options,
            timeout=timeout,
            **fetch_kwargs,
        )
    ):
        posts.append(_serialise_post(post))
        if len(posts) >= limit:
            break

    fetched_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")

    return {
        "platform": "facebook",
        "scraper": "facebook_scraper",
        "target": target_url,
        "target_type": target_type,
        "fetched_at": fetched_at,
        "post_count": len(posts),
        "posts": posts,
    }
