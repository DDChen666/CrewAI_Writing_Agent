"""Fallback scraper for X using public Nitter instances."""
from __future__ import annotations

import datetime as dt
import random
from typing import Any, Dict, List, Optional

import requests


class NitterClient:
    def __init__(
        self,
        instances: List[str],
        timeout: int = 10,
        max_retries: int = 2,
    ) -> None:
        if not instances:
            raise ValueError("At least one Nitter instance must be provided")
        self.instances = instances
        self.timeout = timeout
        self.max_retries = max_retries

    def fetch_user(self, username: str, limit: int = 50, skip_media: bool = False) -> Dict[str, Any]:
        for attempt in range(self.max_retries):
            base = random.choice(self.instances)
            params = {"max": limit}
            try:
                response = requests.get(
                    f"{base.rstrip('/')}/api/user/{username.strip('@')}",
                    params=params,
                    timeout=self.timeout,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; scraper-bot/1.0)"},
                )
                response.raise_for_status()
                payload = response.json()
                items = self._normalize_payload(payload, skip_media=skip_media)
                return {
                    "platform": "x",
                    "account": username,
                    "scraped_at": dt.datetime.utcnow().isoformat(),
                    "items": items,
                    "source": "nitter",
                    "instance": base,
                }
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
        raise RuntimeError("Unable to fetch data from Nitter instances")

    def _normalize_payload(self, payload: Dict[str, Any], skip_media: bool) -> List[Dict[str, Any]]:
        tweets: List[Dict[str, Any]] = []
        for tweet in payload.get("tweets", []):
            media_assets = tweet.get("media", [])
            if skip_media and media_assets:
                continue
            tweets.append(
                {
                    "id": tweet.get("id"),
                    "url": tweet.get("url"),
                    "content": tweet.get("text"),
                    "created_at": tweet.get("date"),
                    "author": tweet.get("username"),
                    "statistics": {
                        "likes": tweet.get("stats", {}).get("likes"),
                        "replies": tweet.get("stats", {}).get("comments"),
                        "retweets": tweet.get("stats", {}).get("retweets"),
                        "quotes": tweet.get("stats", {}).get("quotes"),
                    },
                    "thread": tweet.get("thread", []),
                    "media": media_assets,
                }
            )
        return tweets


def scrape_x_via_nitter(
    username: str,
    instances: List[str],
    limit: int,
    skip_media: bool,
    timeout: int = 10,
    max_retries: int = 2,
) -> Dict[str, Any]:
    client = NitterClient(instances=instances, timeout=timeout, max_retries=max_retries)
    return client.fetch_user(username=username, limit=limit, skip_media=skip_media)
