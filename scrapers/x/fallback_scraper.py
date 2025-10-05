"""Fallback scraper for X using public Nitter instances."""
from __future__ import annotations

import datetime as dt
import random
import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
        session = self._build_session()
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            for base in random.sample(self.instances, k=len(self.instances)):
                params = {"max": limit}
                try:
                    response = session.get(
                        f"{base.rstrip('/')}/api/user/{username.strip('@')}",
                        params=params,
                        timeout=self.timeout,
                        headers={
                            "User-Agent": _random_ua(),
                            "Accept": "application/json",
                        },
                    )
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait_for = int(retry_after)
                            except ValueError:
                                wait_for = 1
                        else:
                            wait_for = 1
                        time.sleep(min(8, wait_for))
                        continue

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
                except requests.RequestException as exc:
                    last_error = exc
                    continue
                except ValueError as exc:
                    last_error = exc
                    continue
            if attempt < self.max_retries - 1:
                time.sleep(min(8, 0.5 * (2 ** attempt)))
        if last_error:
            raise RuntimeError("Unable to fetch data from Nitter instances") from last_error
        raise RuntimeError("Unable to fetch data from Nitter instances")

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=self.max_retries,
            backoff_factor=0.6,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

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


def _random_ua() -> str:
    candidates = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    return random.choice(candidates)
