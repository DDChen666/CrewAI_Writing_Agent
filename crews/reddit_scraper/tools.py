"""Custom CrewAI tools that expose Reddit scraping capabilities."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type
from typing import Literal, Union

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, model_validator

from scrapers.reddit.main_scraper import fetch_subreddit_posts
from scrapers.reddit.oauth_client import RedditOAuthClient


class _ToolExecutionRegistry:
    """In-memory log capturing the raw payloads returned by tool executions."""

    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []

    def reset(self) -> None:
        self._entries.clear()

    def record(self, tool_name: str, payload: Any, metadata: Optional[Dict[str, Any]] = None) -> int:
        entry: Dict[str, Any] = {"tool": tool_name, "payload": payload}
        if metadata is not None:
            entry["metadata"] = metadata
        self._entries.append(entry)
        return len(self._entries)

    def all(self) -> List[Dict[str, Any]]:
        return list(self._entries)


_TOOL_EXECUTION_REGISTRY = _ToolExecutionRegistry()


def reset_tool_execution_log() -> None:
    """Clear the captured tool outputs for a new agent run."""

    _TOOL_EXECUTION_REGISTRY.reset()


def get_tool_execution_log() -> List[Dict[str, Any]]:
    """Return a copy of all tool payloads captured during the current run."""

    return _TOOL_EXECUTION_REGISTRY.all()


def _record_tool_success(
    tool_name: str,
    payload: Any,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    result_id = _TOOL_EXECUTION_REGISTRY.record(tool_name, payload, metadata)
    response: Dict[str, Any] = {"status": "success", "result_id": result_id, "tool": tool_name}
    if metadata:
        response["details"] = metadata
    return json.dumps(response, ensure_ascii=False)


def _record_tool_error(tool_name: str, message: str, *, metadata: Optional[Dict[str, Any]] = None) -> str:
    payload: Dict[str, Any] = {"status": "error", "message": message, "tool": tool_name}
    if metadata:
        payload["details"] = metadata
    _TOOL_EXECUTION_REGISTRY.record(tool_name, payload, metadata)
    return json.dumps(payload, ensure_ascii=False)


class SubredditToolArgs(BaseModel):
    subreddit: str = Field(..., description="Subreddit name or identifier")
    limit: int = Field(50, description="Number of posts to fetch", ge=1, le=500)
    sort: Literal["hot", "new", "top", "rising", "controversial", "best"] = Field(
        "new",
        description="Sort order for subreddit listings",
    )
    time_filter: Optional[Literal["hour", "day", "week", "month", "year", "all"]] = Field(
        None,
        description="Time filter to apply when sort is 'top'",
    )
    comment_depth: Union[int, Literal["all"]] = Field(
        2,
        description="Depth of comments to include; provide an integer or 'all' to fully expand",
    )
    skip_media: bool = Field(False, description="Whether to skip posts containing media")
    timeout: int = Field(10, description="Request timeout in seconds", ge=1, le=60)

    @model_validator(mode="after")
    def _validate_comment_depth_and_time_filter(self) -> "SubredditToolArgs":
        if isinstance(self.comment_depth, int) and not 0 <= self.comment_depth <= 10:
            raise ValueError("comment_depth must be between 0 and 10 when provided as an integer")
        if self.comment_depth == "all" and self.sort in {"hot", "rising"}:
            # no restriction, but leave note for completeness (no error)
            pass
        if self.time_filter and self.sort not in {"top", "best"}:
            raise ValueError("time_filter can only be used when sort is 'top' or 'best'")
        return self


class APIToolArgs(BaseModel):
    endpoint: str = Field(..., description="Relative or absolute Reddit API endpoint")
    method: str = Field("GET", description="HTTP method to use")
    params: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    data: Optional[Dict[str, Any]] = Field(None, description="Form payload for POST requests")
    json_body: Optional[Any] = Field(None, alias="json", description="JSON payload for POST requests")
    timeout: int = Field(10, description="Request timeout in seconds", ge=1, le=60)

    class Config:
        populate_by_name = True


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
        sort: str = "new",
        time_filter: Optional[str] = None,
        comment_depth: Union[int, Literal["all"]] = 2,
        skip_media: bool = False,
        timeout: int = 10,
    ) -> str:
        requested_sort = sort
        normalized_sort = "top" if sort == "best" else sort
        effective_time_filter = time_filter
        metadata: Dict[str, Any] = {
            "subreddit": subreddit,
            "limit": limit,
            "sort_requested": requested_sort,
            "sort_used": normalized_sort,
            "comment_depth": comment_depth,
            "skip_media": skip_media,
            "timeout": timeout,
        }
        if time_filter:
            metadata["time_filter_requested"] = time_filter
        if sort == "best" and not effective_time_filter:
            effective_time_filter = "day"
            metadata["time_filter_defaulted"] = "day"
        if normalized_sort != "top":
            effective_time_filter = None
        if effective_time_filter:
            metadata["time_filter"] = effective_time_filter

        try:
            payload = fetch_subreddit_posts(
                subreddit=subreddit,
                limit=limit,
                skip_media=skip_media,
                comment_depth=comment_depth,
                timeout=timeout,
                sort=normalized_sort,
                time_filter=effective_time_filter,
            )
        except Exception as exc:  # pragma: no cover - network failure path
            return _record_tool_error(self.name, str(exc), metadata=metadata)

        return _record_tool_success(self.name, payload, metadata=metadata)


class RedditAPITool(BaseTool):
    name: str = "reddit_api_gateway"
    description: str = (
        "Call any Reddit Data API endpoint using OAuth client credentials. Use this "
        "for actions other than subreddit listing fetches (for example user profiles, "
        "moderation data, or metadata endpoints). For user lookups, pair calls to "
        "/user/{name}/about and /user/{name}/submitted."
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
            return _record_tool_error(self.name, str(exc))

        return _record_tool_success(self.name, response)


reddit_subreddit_tool = RedditSubredditTool()
reddit_api_tool = RedditAPITool()
