"""Primary scraper for Reddit using the official Data API."""
from __future__ import annotations

import datetime as dt
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth

try:  # Lazy import so the module still loads if python-dotenv is unavailable.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only triggered when dependency missing.
    load_dotenv = None

if load_dotenv:
    load_dotenv()


class RedditAPIClient:
    """Thin wrapper around the OAuth-based Reddit Data API."""

    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    API_BASE = "https://oauth.reddit.com"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        timeout: int = 10,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    def _ensure_token(self) -> None:
        if self._token and time.time() < self._token_expiry - 10:
            return

        response = requests.post(
            self.TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in", 3600)
        if not access_token:
            raise RuntimeError("Reddit API did not return an access token")

        self._token = access_token
        self._token_expiry = time.time() + int(expires_in)

    def _build_headers(self) -> Dict[str, str]:
        self._ensure_token()
        return {
            "User-Agent": self.user_agent,
            "Authorization": f"Bearer {self._token}",
        }

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = path if path.startswith("http") else f"{self.API_BASE}{path}"
        response = requests.get(url, headers=self._build_headers(), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


def _load_credentials() -> Tuple[str, str, str]:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")

    missing = [
        name
        for name, value in (
            ("REDDIT_CLIENT_ID", client_id),
            ("REDDIT_CLIENT_SECRET", client_secret),
            ("REDDIT_USER_AGENT", user_agent),
        )
        if not value
    ]
    if missing:
        raise EnvironmentError(
            "Missing Reddit API credentials: " + ", ".join(missing) + ". "
            "Populate them in your environment or .env file."
        )

    return client_id, client_secret, user_agent


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


def _fetch_comments(client: RedditAPIClient, permalink: str, depth: int) -> List[Dict[str, Any]]:
    if not permalink:
        return []
    path = f"{permalink.rstrip('/')}.json"
    payload = client.get(path, params={"limit": 50, "depth": depth, "raw_json": 1})
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
    client_id, client_secret, user_agent = _load_credentials()
    client = RedditAPIClient(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        timeout=timeout,
    )

    posts: List[Dict[str, Any]] = []
    after: Optional[str] = None

    while len(posts) < limit:
        params = {
            "limit": min(limit - len(posts), 100),
            "after": after,
            "raw_json": 1,
        }
        params = {key: value for key, value in params.items() if value is not None}
        data = client.get(f"/r/{subreddit}/new", params=params).get("data", {})
        children = data.get("children", [])
        for child in children:
            post_data = child.get("data", {})
            if skip_media and _has_media(post_data):
                continue

            comments = _fetch_comments(client, post_data.get("permalink", ""), depth=comment_depth)

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
