"""Primary scraper for Reddit using the official OAuth Data API."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from .oauth_client import RedditOAuthClient


def _has_media(post_data: Dict[str, Any]) -> bool:
    if post_data.get("is_video"):
        return True
    if post_data.get("post_hint") in {"image", "hosted:video", "rich:video"}:
        return True
    if post_data.get("media_metadata") or post_data.get("gallery_data"):
        return True
    if post_data.get("url_overridden_by_dest") and post_data.get("url_overridden_by_dest").startswith(
        "https://i.redd.it"
    ):
        return True
    return False


def _fetch_comments(
    client: RedditOAuthClient,
    permalink: str,
    *,
    depth: int,
    timeout: int,
) -> List[Dict[str, Any]]:
    if not permalink:
        return []

    endpoint = f"{permalink}.json" if permalink.startswith("/r/") else permalink
    payload = client.get(endpoint, params={"depth": depth, "limit": 50}, timeout=timeout)

    if not isinstance(payload, list) or len(payload) < 2:
        return []

    comment_listing = payload[1].get("data", {}).get("children", [])
    comments: List[Dict[str, Any]] = []
    for comment in comment_listing:
        if comment.get("kind") != "t1":
            continue
        data = comment.get("data", {})
        comments.append(
            {
                "id": data.get("id"),
                "author": data.get("author"),
                "body": data.get("body"),
                "score": data.get("score"),
                "created_utc": data.get("created_utc"),
            }
        )
    return comments


def fetch_subreddit_posts(
    subreddit: str,
    limit: int = 50,
    skip_media: bool = False,
    comment_depth: int = 2,
    timeout: int = 10,
    *,
    client: Optional[RedditOAuthClient] = None,
) -> Dict[str, Any]:
    """Fetch posts from a subreddit using the official OAuth API."""

    oauth_client = client or RedditOAuthClient(timeout=timeout)

    posts: List[Dict[str, Any]] = []
    after: Optional[str] = None

    while len(posts) < limit:
        params: Dict[str, Any] = {"limit": min(100, limit - len(posts))}
        if after:
            params["after"] = after

        listing = oauth_client.get(f"/r/{subreddit}/new", params=params, timeout=timeout)
        data = listing.get("data", {}) if isinstance(listing, dict) else {}
        children = data.get("children", [])

        if not children:
            break

        for child in children:
            post_data = child.get("data", {})
            if skip_media and _has_media(post_data):
                continue

            comments = _fetch_comments(
                oauth_client,
                post_data.get("permalink", ""),
                depth=comment_depth,
                timeout=timeout,
            )

            posts.append(
                {
                    "id": post_data.get("id"),
                    "permalink": f"https://www.reddit.com{post_data.get('permalink')}",
                    "title": post_data.get("title"),
                    "selftext": post_data.get("selftext"),
                    "created_utc": post_data.get("created_utc"),
                    "author": post_data.get("author"),
                    "statistics": {
                        "score": post_data.get("score"),
                        "upvote_ratio": post_data.get("upvote_ratio"),
                        "num_comments": post_data.get("num_comments"),
                    },
                    "flair": post_data.get("link_flair_text"),
                    "over_18": post_data.get("over_18"),
                    "url": post_data.get("url"),
                    "media": {
                        "is_video": post_data.get("is_video"),
                        "post_hint": post_data.get("post_hint"),
                        "preview": post_data.get("preview"),
                    },
                    "comments": comments,
                }
            )

            if len(posts) >= limit:
                break

        after = data.get("after")
        if not after:
            break

    return {
        "platform": "reddit",
        "subreddit": subreddit,
        "scraped_at": dt.datetime.utcnow().isoformat(),
        "items": posts,
        "source": "reddit_api",
    }
