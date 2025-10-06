"""Fallback scraper for Reddit using the PullPush API.

This path only provides subreddit listings ordered by ``created_utc`` descending
and never includes comment threads or alternative sort orders.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List

import requests


class PullPushClient:
    def __init__(self, base_url: str, timeout: int = 10, max_retries: int = 2) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def fetch(
        self,
        subreddit: str,
        limit: int = 50,
        skip_media: bool = False,
    ) -> Dict[str, Any]:
        size = min(limit, 100)
        params = {
            "subreddit": subreddit,
            "sort": "desc",
            "sort_type": "created_utc",
            "size": size,
        }

        posts: List[Dict[str, Any]] = []
        cursor = None
        while len(posts) < limit:
            if cursor:
                params["before"] = cursor
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            results = data.get("data", [])
            if not results:
                break

            for post in results:
                media_present = bool(post.get("media") or post.get("thumbnail"))
                if skip_media and media_present:
                    continue

                posts.append(
                    {
                        "id": post.get("id"),
                        "permalink": f"https://www.reddit.com{post.get('permalink')}",
                        "title": post.get("title"),
                        "selftext": post.get("selftext"),
                        "created_utc": post.get("created_utc"),
                        "author": post.get("author"),
                        "statistics": {
                            "score": post.get("score"),
                            "upvote_ratio": post.get("upvote_ratio"),
                            "num_comments": post.get("num_comments"),
                        },
                        "flair": post.get("link_flair_text"),
                        "over_18": post.get("over_18"),
                        "url": post.get("url"),
                        "media": post.get("media"),
                        "comments": [],
                    }
                )

                if len(posts) >= limit:
                    break

            cursor = results[-1].get("created_utc")
            if cursor is None:
                break

        return {
            "platform": "reddit",
            "subreddit": subreddit,
            "scraped_at": dt.datetime.utcnow().isoformat(),
            "items": posts,
            "source": "pullpush",
            "parameters": {
                "sort": "created_utc_desc",
                "comments": "not_available",
                "skip_media": skip_media,
            },
            "notes": "OAuth scraper unavailable; used PullPush fallback (no comments).",
        }


def scrape_reddit_via_pullpush(
    subreddit: str,
    base_url: str,
    limit: int,
    skip_media: bool,
    timeout: int = 10,
    max_retries: int = 2,
) -> Dict[str, Any]:
    client = PullPushClient(base_url=base_url, timeout=timeout, max_retries=max_retries)
    return client.fetch(subreddit=subreddit, limit=limit, skip_media=skip_media)
