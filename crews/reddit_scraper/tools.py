"""Custom CrewAI tools that expose Reddit scraping capabilities."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from scrapers.reddit.main_scraper import fetch_subreddit_posts
from scrapers.reddit.oauth_client import RedditOAuthClient


class SubredditToolArgs(BaseModel):
    subreddit: str = Field(..., description="Subreddit name or identifier")
    limit: int = Field(50, description="Number of posts to fetch", ge=1, le=500)
    skip_media: bool = Field(False, description="Whether to skip posts containing media")
    comment_depth: int = Field(2, description="Depth of comments to include", ge=0, le=10)
    timeout: int = Field(10, description="Request timeout in seconds", ge=1, le=60)


class APIToolArgs(BaseModel):
    endpoint: str = Field(..., description="Relative or absolute Reddit API endpoint")
    method: str = Field("GET", description="HTTP method to use")
    params: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    data: Optional[Dict[str, Any]] = Field(None, description="Form payload for POST requests")
    json_body: Optional[Any] = Field(None, alias="json", description="JSON payload for POST requests")
    timeout: int = Field(10, description="Request timeout in seconds", ge=1, le=60)

    class Config:
        populate_by_name = True


def _error_payload(message: str) -> str:
    return json.dumps({"status": "error", "message": message}, ensure_ascii=False)


class RedditSubredditTool(BaseTool):
    name: str = "reddit_subreddit_fetcher"
    description: str = (
        "Use this tool to fetch structured submissions and comments from a subreddit "
        "via the official Reddit Data API."
    )
    args_schema: Type[BaseModel] = SubredditToolArgs

    def _run(  # type: ignore[override]
        self,
        subreddit: str,
        limit: int = 50,
        skip_media: bool = False,
        comment_depth: int = 2,
        timeout: int = 10,
    ) -> str:
        try:
            payload = fetch_subreddit_posts(
                subreddit=subreddit,
                limit=limit,
                skip_media=skip_media,
                comment_depth=comment_depth,
                timeout=timeout,
            )
        except Exception as exc:  # pragma: no cover - network failure path
            return _error_payload(str(exc))

        return json.dumps(payload, ensure_ascii=False)


class RedditAPITool(BaseTool):
    name: str = "reddit_api_gateway"
    description: str = (
        "Call any Reddit Data API endpoint using OAuth client credentials. Use this "
        "for actions other than subreddit listing fetches."
    )
    args_schema: Type[BaseModel] = APIToolArgs

    def __init__(self) -> None:
        super().__init__()
        self._client: Optional[RedditOAuthClient] = None

    def _get_client(self) -> RedditOAuthClient:
        if self._client is None:
            self._client = RedditOAuthClient()
        return self._client

    def _run(  # type: ignore[override]
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        timeout: int = 10,
    ) -> str:
        try:
            response = self._get_client().request_json(
                method.upper(),
                endpoint,
                params=params,
                data=data,
                json=json_body,
                timeout=timeout,
            )
        except Exception as exc:  # pragma: no cover - network failure path
            return _error_payload(str(exc))

        return json.dumps(response, ensure_ascii=False)


reddit_subreddit_tool = RedditSubredditTool()
reddit_api_tool = RedditAPITool()
