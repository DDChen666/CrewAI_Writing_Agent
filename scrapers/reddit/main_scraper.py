"""Primary scraper for Reddit using the public JSON endpoints."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

import requests


USER_AGENT = "Mozilla/5.0 (compatible; scraper-bot/1.0)"


def _build_listing_url(subreddit: str, limit: int, after: Optional[str] = None) -> str:
    base = f"https://www.reddit.com/r/{subreddit}/new.json"
    params = {"limit": min(limit, 100)}
    if after:
        params["after"] = after
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{base}?{query}"


def _has_media(post_data: Dict[str, Any]) -> bool:
    if post_data.get("is_video"):
        return True
    if post_data.get("post_hint") in {"image", "hosted:video", "rich:video"}:
        return True
    if post_data.get("media_metadata") or post_data.get("gallery_data"):
        return True
    if post_data.get("url_overridden_by_dest") and post_data.get("url_overridden_by_dest").startswith("https://i.redd.it"):
        return True
    return False


def _fetch_comments(permalink: str, depth: int, timeout: int) -> List[Dict[str, Any]]:
    url = f"https://www.reddit.com{permalink}.json?limit=50&depth={depth}"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if len(payload) < 2:
        return []
    comment_listing = payload[1].get("data", {}).get("children", [])
    return [
        {
            "id": comment.get("data", {}).get("id"),
            "author": comment.get("data", {}).get("author"),
            "body": comment.get("data", {}).get("body"),
            "score": comment.get("data", {}).get("score"),
            "created_utc": comment.get("data", {}).get("created_utc"),
        }
        for comment in comment_listing
        if comment.get("kind") == "t1"
    ]


def fetch_subreddit_posts(
    subreddit: str,
    limit: int = 50,
    skip_media: bool = False,
    comment_depth: int = 2,
    timeout: int = 10,
) -> Dict[str, Any]:
    posts: List[Dict[str, Any]] = []
    after: Optional[str] = None

    while len(posts) < limit:
        url = _build_listing_url(subreddit, limit - len(posts), after)
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
        data = response.json().get("data", {})
        children = data.get("children", [])
        for child in children:
            post_data = child.get("data", {})
            if skip_media and _has_media(post_data):
                continue

            comments = _fetch_comments(post_data.get("permalink", ""), depth=comment_depth, timeout=timeout)

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
        "source": "reddit_json",
    }
