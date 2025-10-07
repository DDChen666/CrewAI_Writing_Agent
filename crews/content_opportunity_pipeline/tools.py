"""Tools supporting the Content Opportunity Pipeline."""
from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Type
from typing import Literal

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, RootModel, ValidationError

# ---------------------------------------------------------------------------
# Dataset registry utilities
# ---------------------------------------------------------------------------

@dataclass
class _StoredDataset:
    """Internal representation of a dataset stored in memory."""

    dataset_id: str
    summaries: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    raw_items: Dict[str, Dict[str, Any]]
    normalised_cache: Dict[Tuple[str, Tuple[str, ...]], Dict[str, Any]] = field(default_factory=dict)
    comment_cache: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._pointer_index: Dict[str, Dict[str, Any]] = {}
        self._post_id_index: Dict[str, str] = {}
        self._pointer_sequence: List[str] = []
        for summary in self.summaries:
            pointer_info = summary.setdefault("raw_pointer", {})
            pointer = pointer_info.get("post_pointer")
            if not pointer:
                pointer = str(uuid.uuid4())
                pointer_info["post_pointer"] = pointer
            pointer_info["dataset_id"] = self.dataset_id
            summary["dataset_id"] = self.dataset_id
            self._pointer_index[pointer] = summary
            self._pointer_sequence.append(pointer)
            post_id = summary.get("post_id")
            if post_id is not None:
                self._post_id_index[str(post_id)] = pointer
        # Ensure raw item pointers are aligned with summaries
        for pointer in list(self.raw_items.keys()):
            if pointer not in self._pointer_index:
                logging.debug("Removing raw item without summary pointer: %s", pointer)
                self.raw_items.pop(pointer)

    def iter_summaries(self) -> List[Dict[str, Any]]:
        return [copy.deepcopy(summary) for summary in self.summaries]

    def lookup_pointer(self, post_id: str) -> Optional[str]:
        return self._post_id_index.get(str(post_id))

    def summaries_for_pointers(self, pointers: Sequence[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for pointer in pointers:
            summary = self._pointer_index.get(pointer)
            if summary:
                results.append(copy.deepcopy(summary))
        return results

    def raw_for_pointer(self, pointer: str) -> Optional[Dict[str, Any]]:
        payload = self.raw_items.get(pointer)
        if payload is None:
            return None
        return copy.deepcopy(payload)

    def summary_for_pointer(self, pointer: str) -> Optional[Dict[str, Any]]:
        summary = self._pointer_index.get(pointer)
        return copy.deepcopy(summary) if summary is not None else None

    def pointer_sequence(self) -> List[str]:
        return list(self._pointer_sequence)

    def cache_normalised(self, pointer: str, extra_fields: Tuple[str, ...], payload: Dict[str, Any]) -> None:
        self.normalised_cache[(pointer, extra_fields)] = copy.deepcopy(payload)

    def get_cached_normalised(self, pointer: str, extra_fields: Tuple[str, ...]) -> Optional[Dict[str, Any]]:
        cached = self.normalised_cache.get((pointer, extra_fields))
        return copy.deepcopy(cached) if cached is not None else None

    def cache_comments(self, pointer: str, comments: List[Dict[str, Any]]) -> None:
        self.comment_cache[pointer] = copy.deepcopy(comments)

    def get_cached_comments(self, pointer: str) -> Optional[List[Dict[str, Any]]]:
        cached = self.comment_cache.get(pointer)
        return copy.deepcopy(cached) if cached is not None else None


class _DatasetStore:
    """In-memory dataset store underpinning the analysis sandbox."""

    def __init__(self) -> None:
        self._datasets: Dict[str, _StoredDataset] = {}

    def new_dataset_id(self) -> str:
        dataset_id = str(uuid.uuid4())
        while dataset_id in self._datasets:
            dataset_id = str(uuid.uuid4())
        return dataset_id

    def store(
        self,
        dataset_id: str,
        summaries: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        raw_items: Dict[str, Dict[str, Any]],
    ) -> str:
        stored = _StoredDataset(
            dataset_id=dataset_id,
            summaries=summaries,
            metadata=metadata,
            raw_items=raw_items,
        )
        self._datasets[dataset_id] = stored
        return dataset_id

    def get(self, dataset_id: str) -> _StoredDataset:
        try:
            return self._datasets[dataset_id]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unknown dataset_id: {dataset_id}") from exc

    def drop(self, dataset_id: str) -> None:
        self._datasets.pop(dataset_id, None)

    def summary(self, dataset_id: str) -> Dict[str, Any]:
        dataset = self.get(dataset_id)
        return {
            "dataset_id": dataset_id,
            "item_count": len(dataset.summaries),
            "metadata": dataset.metadata,
        }


_DATASET_STORE = _DatasetStore()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


_DEFAULT_FIELD_MAPPING: Dict[str, Tuple[str, Optional[str]]] = {
    "post_id": ("id", None),
    "title": ("title", None),
    "body": ("selftext", None),
    "permalink": ("permalink", None),
    "url": ("url", None),
    "author": ("author", None),
    "created_utc": ("created_utc", None),
    "score": ("statistics.score", None),
    "upvote_ratio": ("statistics.upvote_ratio", None),
    "num_comments": ("statistics.num_comments", None),
    "flair": ("flair", None),
    "over_18": ("over_18", None),
    "media_post_hint": ("media.post_hint", None),
    "media_is_video": ("media.is_video", None),
}


def _resolve_field(payload: Dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    """Safely resolve a dotted field path from a nested dictionary."""

    current: Any = payload
    for segment in dotted_path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return default
    return current


def _truncate_text(text: Optional[str], length: int = 240) -> Optional[str]:
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    if len(cleaned) <= length:
        return cleaned
    return cleaned[: length - 3].rstrip() + "..."


def _build_post_summary(
    raw_item: Mapping[str, Any],
    *,
    pointer: str,
    dataset_context: Mapping[str, Any],
) -> Dict[str, Any]:
    created_value = raw_item.get("created_utc")
    created_iso: Optional[str] = None
    created_float: Optional[float] = None
    if isinstance(created_value, (int, float)):
        created_float = float(created_value)
        created_iso = datetime.utcfromtimestamp(created_float).isoformat() + "Z"

    score = _resolve_field(raw_item, "statistics.score")
    upvote_ratio = _resolve_field(raw_item, "statistics.upvote_ratio")
    num_comments = _resolve_field(raw_item, "statistics.num_comments")
    comments = raw_item.get("comments")
    top_level_comment_count = len(comments) if isinstance(comments, list) else 0

    summary: Dict[str, Any] = {
        "post_id": raw_item.get("id"),
        "title": raw_item.get("title"),
        "permalink": raw_item.get("permalink"),
        "url": raw_item.get("url"),
        "author": raw_item.get("author"),
        "created_utc": created_float,
        "created_at_iso": created_iso,
        "score": score,
        "upvote_ratio": upvote_ratio,
        "num_comments": num_comments,
        "flair": raw_item.get("flair"),
        "over_18": raw_item.get("over_18"),
        "subreddit": dataset_context.get("subreddit") or raw_item.get("subreddit"),
        "platform": dataset_context.get("platform", "reddit"),
        "body_preview": _truncate_text(raw_item.get("selftext")),
        "top_level_comment_count": top_level_comment_count,
        "raw_pointer": {"post_pointer": pointer},
        "media_post_hint": _resolve_field(raw_item, "media.post_hint"),
        "media_is_video": _resolve_field(raw_item, "media.is_video"),
        "has_media": bool(raw_item.get("media")),
        "source_file": dataset_context.get("source_file"),
        "scraped_at": dataset_context.get("scraped_at"),
        "target": dataset_context.get("target"),
        "statistics": {
            "score": score,
            "upvote_ratio": upvote_ratio,
            "num_comments": num_comments,
        },
    }
    return summary


def _prepare_comment_tree(raw_comment: Mapping[str, Any]) -> Dict[str, Any]:
    created_value = raw_comment.get("created_utc")
    created_iso: Optional[str] = None
    created_float: Optional[float] = None
    if isinstance(created_value, (int, float)):
        created_float = float(created_value)
        created_iso = datetime.utcfromtimestamp(created_float).isoformat() + "Z"
    replies_raw = raw_comment.get("replies")
    replies: List[Dict[str, Any]] = []
    if isinstance(replies_raw, list):
        for child in replies_raw:
            if isinstance(child, Mapping):
                replies.append(_prepare_comment_tree(child))
    comment: Dict[str, Any] = {
        "id": raw_comment.get("id"),
        "author": raw_comment.get("author"),
        "body": raw_comment.get("body"),
        "score": raw_comment.get("score"),
        "created_utc": created_float,
        "created_at_iso": created_iso,
        "replies": replies,
    }
    comment["replies_count"] = len(replies)
    return comment


def _count_comment_tree(comments: Any) -> int:
    if not isinstance(comments, list):
        return 0
    total = 0
    for comment in comments:
        if not isinstance(comment, Mapping):
            continue
        total += 1
        total += _count_comment_tree(comment.get("replies"))
    return total


def _filter_comment_list(
    comments: Sequence[Dict[str, Any]],
    filters: Optional[Sequence[FilterCondition]],
) -> List[Dict[str, Any]]:
    if not filters:
        return [copy.deepcopy(comment) for comment in comments]

    filtered: List[Dict[str, Any]] = []
    for comment in comments:
        include = True
        for condition in filters:
            candidate = _resolve_field(comment, condition.field)
            if not _apply_condition(candidate, operator=condition.operator, expected=condition.value):
                include = False
                break
        # Always evaluate replies so that qualifying children surface even when parent is filtered out.
        replies = _filter_comment_list(comment.get("replies", []), filters)
        working_comment = copy.deepcopy(comment)
        working_comment["replies"] = replies
        working_comment["replies_count"] = len(replies)
        if include or replies:
            filtered.append(working_comment)
    return filtered


def _sort_and_limit_comments(
    comments: List[Dict[str, Any]],
    *,
    sort_by: Optional[str],
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    if sort_by:
        comments.sort(key=lambda item: _resolve_field(item, sort_by), reverse=True)
    if limit is not None:
        return comments[:limit]
    return comments


def _retrieve_comment_tree(
    dataset: _StoredDataset, pointer: str, raw_item: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    cached = dataset.get_cached_comments(pointer)
    if cached is not None:
        return cached
    comments: List[Dict[str, Any]] = []
    raw_comments = raw_item.get("comments")
    if isinstance(raw_comments, list):
        for raw_comment in raw_comments:
            if isinstance(raw_comment, Mapping):
                comments.append(_prepare_comment_tree(raw_comment))
    dataset.cache_comments(pointer, comments)
    cached_after_store = dataset.get_cached_comments(pointer)
    return cached_after_store if cached_after_store is not None else []


def _normalise_post(
    summary: Mapping[str, Any],
    raw_item: Mapping[str, Any],
    *,
    extra_fields: Sequence[str] = (),
    include_comments: bool = False,
    comments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    normalised: Dict[str, Any] = {
        "dataset_id": summary.get("dataset_id"),
        "post_id": summary.get("post_id"),
        "title": summary.get("title"),
        "body": raw_item.get("selftext"),
        "permalink": summary.get("permalink"),
        "url": summary.get("url"),
        "author": summary.get("author"),
        "created_utc": summary.get("created_utc"),
        "created_at_iso": summary.get("created_at_iso"),
        "flair": summary.get("flair"),
        "over_18": summary.get("over_18"),
        "subreddit": summary.get("subreddit"),
        "platform": summary.get("platform", "reddit"),
        "statistics": summary.get("statistics"),
        "raw_pointer": summary.get("raw_pointer"),
        "body_preview": summary.get("body_preview"),
        "top_level_comment_count": summary.get("top_level_comment_count"),
        "media": copy.deepcopy(raw_item.get("media")),
        "target": summary.get("target"),
        "scraped_at": summary.get("scraped_at"),
        "source_file": summary.get("source_file"),
    }

    for output_field, (source_field, _) in _DEFAULT_FIELD_MAPPING.items():
        if output_field in normalised and normalised[output_field] is not None:
            continue
        value = _resolve_field(raw_item, source_field)
        if output_field == "created_utc" and isinstance(value, (int, float)):
            normalised["created_utc"] = float(value)
            normalised["created_at_iso"] = datetime.utcfromtimestamp(float(value)).isoformat() + "Z"
        else:
            normalised[output_field] = value

    for field in extra_fields:
        if field in normalised:
            continue
        normalised[field] = _resolve_field(raw_item, field)

    if include_comments:
        normalised["comments"] = comments or []
    return normalised


def _apply_condition(value: Any, *, operator: str, expected: Any) -> bool:
    """Evaluate a comparison condition."""

    if operator == "exists":
        return value is not None
    if operator == "missing":
        return value is None
    if operator == "is_true":
        return bool(value) is True
    if operator == "is_false":
        return bool(value) is False
    if value is None:
        return False
    if operator == "eq":
        return value == expected
    if operator == "ne":
        return value != expected
    if operator == "gt":
        try:
            return value > expected
        except TypeError:
            return False
    if operator == "ge":
        try:
            return value >= expected
        except TypeError:
            return False
    if operator == "lt":
        try:
            return value < expected
        except TypeError:
            return False
    if operator == "le":
        try:
            return value <= expected
        except TypeError:
            return False
    if operator == "contains":
        if isinstance(value, str) and isinstance(expected, str):
            return expected in value
        if isinstance(value, Iterable):
            return expected in value
        return False
    if operator == "icontains":
        if isinstance(value, str) and isinstance(expected, str):
            return expected.lower() in value.lower()
        return False
    if operator == "startswith":
        if isinstance(value, str) and isinstance(expected, str):
            return value.startswith(expected)
        return False
    if operator == "endswith":
        if isinstance(value, str) and isinstance(expected, str):
            return value.endswith(expected)
        return False
    if operator == "regex":
        if isinstance(value, str) and isinstance(expected, str):
            return re.search(expected, value) is not None
        return False
    if operator == "in":
        if isinstance(expected, (list, tuple, set, frozenset)):
            return value in expected
        return value == expected
    if operator == "not_in":
        if isinstance(expected, (list, tuple, set, frozenset)):
            return value not in expected
        return value != expected
    raise ValueError(f"Unsupported operator: {operator}")


# ---------------------------------------------------------------------------
# Pydantic schemas for tool arguments
# ---------------------------------------------------------------------------


class RedditLocatorArgs(BaseModel):
    base_dir: str = Field("scraepr", description="Root directory that contains scraped JSON files")
    date_prefixes: Optional[List[str]] = Field(
        None,
        description="Specific date directories (YYYYMMDD) to consider. If omitted, search all dates.",
    )
    platform: Optional[str] = Field(None, description="Filter files whose platform matches the provided value")
    limit: int = Field(20, ge=1, le=200, description="Maximum number of files to return")
    sort_by: str = Field(
        "modified",
        description="Sort order for files. Supported values: 'modified', 'name'.",
    )
    descending: bool = Field(True, description="Whether to sort in descending order")


class FieldSelection(RootModel[List[str]]):
    """Helper for validating field selection arrays."""

    root: List[str]


class FilterCondition(BaseModel):
    field: str = Field(..., description="Dotted field path inside the normalised post structure")
    operator: str = Field(
        ...,
        description=(
            "Comparison operator, e.g. eq, ne, gt, ge, lt, le, contains, icontains, startswith, endswith,"
            " regex, in, not_in, exists, missing, is_true, is_false."
        ),
    )
    value: Any = Field(
        None,
        description="Reference value for the comparison. Operators like exists/is_true ignore this field.",
    )


class RedditLoaderArgs(BaseModel):
    file_paths: List[str] = Field(..., description="List of JSON files to load")
    max_items: Optional[int] = Field(
        None,
        description="Hard cap on the number of posts returned after filtering and sorting.",
        ge=1,
        le=2000,
    )
    select_fields: Optional[FieldSelection] = Field(
        None,
        description="Additional dotted fields from the raw JSON payload to surface in the normalised result.",
    )
    sort_by: Optional[str] = Field(
        None,
        description="Field name within the normalised item to sort by (e.g. score, upvote_ratio).",
    )
    descending: bool = Field(True, description="Whether sorting should be descending")
    filters: Optional[List[FilterCondition]] = Field(
        None,
        description="Filtering rules applied after normalisation.",
    )
    drop_removed: bool = Field(
        True,
        description="Exclude posts whose body is '[removed]' or '[deleted]'",
    )


class RedditDatasetFilterArgs(BaseModel):
    dataset_id: str = Field(..., description="Identifier returned from the loader tool")
    filters: Optional[List[FilterCondition]] = Field(None, description="Additional filters to apply")
    sort_by: Optional[str] = Field(None, description="Optional field to sort by")
    descending: bool = Field(True, description="Descending sort order when sort_by is provided")
    limit: Optional[int] = Field(None, ge=1, le=2000, description="Limit the number of rows in the filtered dataset")


class RedditDatasetExportArgs(BaseModel):
    dataset_id: str = Field(..., description="Identifier returned from either the loader or filter tools")
    limit: Optional[int] = Field(None, ge=1, le=2000, description="Limit the number of rows exported")
    include_statistics: bool = Field(
        True,
        description="Include aggregate statistics (score totals, averages, etc.) in the export payload.",
    )


class RedditDatasetLookupArgs(BaseModel):
    dataset_id: str = Field(..., description="Identifier associated with a stored dataset")
    post_ids: Optional[List[str]] = Field(
        None,
        description="Optional list of post_ids to retrieve. When omitted the tool returns the first `limit` items.",
    )
    limit: Optional[int] = Field(
        None,
        ge=1,
        le=500,
        description="Maximum number of posts to return when post_ids is not supplied.",
    )
    include_metadata: bool = Field(False, description="Whether to include dataset metadata in the response")


class ContentExplorerArgs(BaseModel):
    dataset_id: str = Field(..., description="Identifier associated with a stored dataset")
    post_ids: Optional[List[str]] = Field(
        None,
        description="Specific post_ids to inspect. When omitted results follow the dataset ordering with optional limit.",
    )
    limit: Optional[int] = Field(
        None,
        ge=1,
        le=500,
        description="Maximum number of items to return when post_ids is not supplied.",
    )
    data_level: Literal["summary", "normalized", "full_comments", "raw"] = Field(
        "summary",
        description="Controls the data depth returned for each post.",
    )
    include_dataset_metadata: bool = Field(
        False,
        description="Include dataset-level metadata in the response payload.",
    )
    extra_fields: Optional[FieldSelection] = Field(
        None,
        description="Additional dotted raw fields to project into the normalised payload when requested.",
    )
    comment_filters: Optional[List[FilterCondition]] = Field(
        None,
        description="Filters applied to comment payloads when data_level requires comments.",
    )
    comment_sort_by: Optional[str] = Field(
        None,
        description="Field used to sort top-level comments when retrieving comment trees.",
    )
    comment_limit: Optional[int] = Field(
        None,
        ge=1,
        le=200,
        description="Limit the number of top-level comments returned after sorting and filtering.",
    )


class MediaAnalyzerArgs(BaseModel):
    url: str = Field(..., description="Direct URL to an image or video asset to analyse")
    prompt: Optional[str] = Field(
        None,
        description="Optional analysis prompt sent to the Gemini multimodal model. A default prompt is used when omitted.",
    )
    model: str = Field(
        "gemini-1.5-flash",
        description="Gemini model identifier to use for multimodal analysis.",
    )
    download_timeout: int = Field(
        15,
        ge=1,
        le=60,
        description="Timeout in seconds for downloading the media asset before analysis.",
    )


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


class RedditScrapeLocatorTool(BaseTool):
    name: str = "reddit_scrape_locator"
    description: str = (
        "Discover available Reddit scrape JSON files. Use this to identify which files should "
        "be loaded before running any filtering or analysis."
    )
    args_schema: Type[BaseModel] = RedditLocatorArgs

    def _run(  # type: ignore[override]
        self,
        base_dir: str = "scraepr",
        date_prefixes: Optional[List[str]] = None,
        platform: Optional[str] = None,
        limit: int = 20,
        sort_by: str = "modified",
        descending: bool = True,
    ) -> str:
        root = Path(base_dir)
        if not root.exists():
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Directory '{base_dir}' does not exist.",
                    "tool": self.name,
                },
                ensure_ascii=False,
            )

        candidate_paths: List[Path] = []
        date_dirs: Iterable[Path]
        if date_prefixes:
            date_dirs = [root / prefix for prefix in date_prefixes]
        else:
            date_dirs = [p for p in root.iterdir() if p.is_dir()]

        for directory in date_dirs:
            if not directory.exists() or not directory.is_dir():
                continue
            candidate_paths.extend(directory.rglob("*.json"))

        file_infos: List[Dict[str, Any]] = []
        skipped_files: List[Dict[str, str]] = []
        for path in candidate_paths:
            try:
                raw_text = path.read_text(encoding="utf-8")
            except OSError as exc:
                skipped_files.append(
                    {
                        "path": str(path.as_posix()),
                        "reason": f"read_error: {exc.__class__.__name__}",
                    }
                )
                continue

            try:
                payload: Any = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                skipped_files.append(
                    {
                        "path": str(path.as_posix()),
                        "reason": f"json_decode_error: {exc.msg}",
                    }
                )
                continue

            if not isinstance(payload, dict):
                skipped_files.append(
                    {
                        "path": str(path.as_posix()),
                        "reason": f"unsupported_payload_type: {type(payload).__name__}",
                    }
                )
                continue

            if platform and payload.get("platform") != platform:
                continue
            scraped_at = payload.get("scraped_at")
            stat = path.stat()
            items = payload.get("items")
            item_count = len(items) if isinstance(items, list) else 0
            file_infos.append(
                {
                    "path": str(path.as_posix()),
                    "size_bytes": stat.st_size,
                    "modified": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
                    "scraped_at": scraped_at,
                    "subreddit": payload.get("subreddit"),
                    "item_count": item_count,
                }
            )

        if sort_by == "name":
            file_infos.sort(key=lambda info: info["path"], reverse=descending)
        else:
            file_infos.sort(key=lambda info: info["modified"], reverse=descending)

        return json.dumps(
            {
                "status": "success",
                "tool": self.name,
                "count": min(len(file_infos), limit),
                "files": file_infos[:limit],
                "warnings": skipped_files,
            },
            ensure_ascii=False,
        )


class RedditScrapeLoaderTool(BaseTool):
    name: str = "reddit_scrape_loader"
    description: str = (
        "Load Reddit scrape JSON files, normalise their structure and optionally sort or filter the posts."
    )
    args_schema: Type[BaseModel] = RedditLoaderArgs

    def _filter_item(self, item: Mapping[str, Any], filters: Optional[List[FilterCondition]]) -> bool:
        if not filters:
            return True
        for rule in filters:
            candidate = _resolve_field(item, rule.field)
            if not _apply_condition(candidate, operator=rule.operator, expected=rule.value):
                return False
        return True

    def _run(  # type: ignore[override]
        self,
        file_paths: List[str],
        max_items: Optional[int] = None,
        select_fields: Optional[Sequence[str]] = None,
        sort_by: Optional[str] = None,
        descending: bool = True,
        filters: Optional[List[FilterCondition]] = None,
        drop_removed: bool = True,
    ) -> str:
        if not file_paths:
            return json.dumps(
                {"status": "error", "message": "file_paths cannot be empty", "tool": self.name},
                ensure_ascii=False,
            )

        dataset_id = _DATASET_STORE.new_dataset_id()
        extra_fields: Sequence[str] = list(select_fields or [])
        prepared_filters: Optional[List[FilterCondition]] = None
        if filters:
            prepared_filters = []
            for rule in filters:
                if isinstance(rule, FilterCondition):
                    prepared_filters.append(rule)
                elif isinstance(rule, Mapping):
                    try:
                        prepared_filters.append(FilterCondition(**rule))
                    except ValidationError as exc:
                        logging.warning("Failed to parse filter condition %s: %s", rule, exc)
                        return json.dumps(
                            {
                                "status": "error",
                                "message": "Invalid filter specification supplied to reddit_scrape_loader.",
                                "tool": self.name,
                            },
                            ensure_ascii=False,
                        )
                else:
                    logging.warning(
                        "Unsupported filter type %s supplied to reddit_scrape_loader",
                        type(rule).__name__,
                    )
                    return json.dumps(
                        {
                            "status": "error",
                            "message": "Invalid filter specification supplied to reddit_scrape_loader.",
                            "tool": self.name,
                        },
                        ensure_ascii=False,
                    )
        summaries: List[Dict[str, Any]] = []
        raw_items: Dict[str, Dict[str, Any]] = {}
        source_files: List[str] = []
        subreddits: List[str] = []
        users: List[str] = []
        targets: List[str] = []
        scraped_at_values: List[str] = []
        score_values: List[float] = []
        comment_totals: List[int] = []
        deep_comment_count = 0

        for raw_path in file_paths:
            path = Path(raw_path)
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logging.warning("Failed to load scrape file %s", path)
                continue
            if payload.get("platform") != "reddit":
                continue

            dataset_context = {
                "platform": payload.get("platform"),
                "subreddit": payload.get("subreddit"),
                "target": payload.get("target"),
                "scraped_at": payload.get("scraped_at"),
                "source_file": str(path.as_posix()),
            }

            source_files.append(dataset_context["source_file"])
            if dataset_context["subreddit"]:
                subreddits.append(dataset_context["subreddit"])
            if payload.get("user"):
                users.append(payload.get("user"))
            target = payload.get("target")
            if isinstance(target, Mapping) and target.get("name"):
                targets.append(str(target["name"]))
            scraped_at = payload.get("scraped_at")
            if scraped_at:
                scraped_at_values.append(str(scraped_at))

            items_payload = payload.get("items")
            if not isinstance(items_payload, list):
                continue

            for raw_item in items_payload:
                if not isinstance(raw_item, Mapping):
                    continue
                pointer = str(uuid.uuid4())
                raw_items[pointer] = copy.deepcopy(dict(raw_item))
                summary = _build_post_summary(raw_item, pointer=pointer, dataset_context=dataset_context)
                if drop_removed and isinstance(raw_item.get("selftext"), str):
                    body_value = raw_item.get("selftext", "").strip().lower()
                    if body_value in {"[removed]", "[deleted]"}:
                        # Even though we keep the raw item for traceability, we flag the summary for downstream filtering.
                        summary["body_removed"] = True
                # Attach any additional select fields directly to the summary for quick reference.
                for field in extra_fields:
                    if field in summary:
                        continue
                    summary[field] = _resolve_field(raw_item, field)
                # Aggregate statistics for the overview report.
                score_val = summary.get("score")
                if isinstance(score_val, (int, float)):
                    score_values.append(float(score_val))
                comment_total = summary.get("num_comments")
                if isinstance(comment_total, (int, float)):
                    comment_totals.append(int(comment_total))
                deep_comment_count += _count_comment_tree(raw_item.get("comments"))
                summaries.append(summary)

        if sort_by:
            summaries.sort(key=lambda itm: _resolve_field(itm, sort_by), reverse=descending)

        overview_highlights: Dict[str, Any] = {}
        if summaries:
            overview_highlights = {
                "total_posts_indexed": len(summaries),
                "total_top_level_comments": int(sum(comment_totals)) if comment_totals else 0,
                "total_comment_depth": int(deep_comment_count),
                "score_max": max(score_values) if score_values else None,
                "score_min": min(score_values) if score_values else None,
                "score_average": (sum(score_values) / len(score_values)) if score_values else None,
                "comment_average": (sum(comment_totals) / len(comment_totals)) if comment_totals else None,
                "subreddits": sorted({sub for sub in subreddits if sub}),
                "users": sorted({usr for usr in users if usr}),
                "targets": sorted({tgt for tgt in targets if tgt}),
                "source_files": source_files,
                "scrape_window": {
                    "earliest": min(scraped_at_values) if scraped_at_values else None,
                    "latest": max(scraped_at_values) if scraped_at_values else None,
                },
            }

        dataset_metadata: Dict[str, Any] = {
            "source_files": source_files,
            "subreddits": sorted({sub for sub in subreddits if sub}),
            "users": sorted({usr for usr in users if usr}),
            "targets": sorted({tgt for tgt in targets if tgt}),
            "fields": list(_DEFAULT_FIELD_MAPPING.keys()) + list(extra_fields),
            "total_items": len(summaries),
            "overview": overview_highlights,
        }

        _DATASET_STORE.store(dataset_id, summaries, dataset_metadata, raw_items)

        preview_items = summaries[: min(len(summaries), 5)]

        focus_view: Optional[List[Dict[str, Any]]] = None
        if prepared_filters or max_items is not None:
            filtered_candidates = [summary for summary in summaries if self._filter_item(summary, prepared_filters)]
            if max_items is not None:
                filtered_candidates = filtered_candidates[:max_items]
            focus_view = filtered_candidates

        payload: Dict[str, Any] = {
            "status": "success",
            "tool": self.name,
            "dataset_id": dataset_id,
            "indexed_item_count": len(summaries),
            "preview": preview_items,
            "metadata": dataset_metadata,
        }
        if focus_view is not None:
            payload["focus_view"] = focus_view

        return json.dumps(payload, ensure_ascii=False)


class RedditDatasetFilterTool(BaseTool):
    name: str = "reddit_dataset_filter"
    description: str = "Apply additional filters or sorting to a stored dataset and return a new dataset identifier."
    args_schema: Type[BaseModel] = RedditDatasetFilterArgs

    def _run(  # type: ignore[override]
        self,
        dataset_id: str,
        filters: Optional[List[FilterCondition]] = None,
        sort_by: Optional[str] = None,
        descending: bool = True,
        limit: Optional[int] = None,
    ) -> str:
        try:
            dataset = _DATASET_STORE.get(dataset_id)
        except ValueError as exc:
            return json.dumps(
                {"status": "error", "message": str(exc), "tool": self.name},
                ensure_ascii=False,
            )

        working_items = dataset.iter_summaries()

        if filters:
            filtered: List[Dict[str, Any]] = []
            for item in working_items:
                include = True
                for rule in filters:
                    candidate = _resolve_field(item, rule.field)
                    if not _apply_condition(candidate, operator=rule.operator, expected=rule.value):
                        include = False
                        break
                if include:
                    filtered.append(item)
            working_items = filtered

        if sort_by:
            working_items.sort(key=lambda itm: _resolve_field(itm, sort_by), reverse=descending)

        if limit is not None:
            working_items = working_items[:limit]

        pointers: List[str] = []
        for item in working_items:
            pointer = _resolve_field(item, "raw_pointer.post_pointer")
            if isinstance(pointer, str):
                pointers.append(pointer)

        raw_subset: Dict[str, Dict[str, Any]] = {}
        for pointer in pointers:
            raw_payload = dataset.raw_for_pointer(pointer)
            if raw_payload is not None:
                raw_subset[pointer] = raw_payload

        new_metadata = dict(dataset.metadata)
        new_metadata.update(
            {
                "filtered_from": dataset_id,
                "total_items": len(working_items),
                "applied_filters": [f.model_dump() for f in filters] if filters else None,
                "sort_by": sort_by,
                "descending": descending,
                "limit": limit,
            }
        )
        if not filters:
            new_metadata.pop("applied_filters", None)

        new_dataset_id = _DATASET_STORE.new_dataset_id()
        _DATASET_STORE.store(new_dataset_id, working_items, new_metadata, raw_subset)

        preview = working_items[: min(len(working_items), 5)]

        return json.dumps(
            {
                "status": "success",
                "tool": self.name,
                "dataset_id": new_dataset_id,
                "item_count": len(working_items),
                "preview": preview,
                "metadata": new_metadata,
            },
            ensure_ascii=False,
        )


class RedditDatasetExportTool(BaseTool):
    name: str = "reddit_dataset_exporter"
    description: str = (
        "Produce a cleaned content stream payload from a stored dataset so downstream agents can consume it."
    )
    args_schema: Type[BaseModel] = RedditDatasetExportArgs

    def _run(  # type: ignore[override]
        self,
        dataset_id: str,
        limit: Optional[int] = None,
        include_statistics: bool = True,
    ) -> str:
        try:
            dataset = _DATASET_STORE.get(dataset_id)
        except ValueError as exc:
            return json.dumps(
                {"status": "error", "message": str(exc), "tool": self.name},
                ensure_ascii=False,
            )

        items = dataset.iter_summaries()
        if limit is not None:
            items = items[:limit]

        export_payload: Dict[str, Any] = {
            "status": "success",
            "tool": self.name,
            "dataset_id": dataset_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "content_stream": {
                "platform": "reddit",
                "source_files": dataset.metadata.get("source_files", []),
                "subreddits": dataset.metadata.get("subreddits", []),
                "item_count": len(items),
                "items": items,
            },
        }

        if include_statistics:
            scores = [item.get("score") for item in items if isinstance(item.get("score"), (int, float))]
            upvote_ratios = [
                item.get("upvote_ratio") for item in items if isinstance(item.get("upvote_ratio"), (int, float))
            ]
            comment_counts = [
                item.get("num_comments") for item in items if isinstance(item.get("num_comments"), (int, float))
            ]

            def _safe_average(values: Sequence[float]) -> Optional[float]:
                return float(sum(values) / len(values)) if values else None

            export_payload["content_stream"]["statistics"] = {
                "score_total": float(sum(scores)) if scores else 0.0,
                "score_average": _safe_average(scores),
                "upvote_ratio_average": _safe_average(upvote_ratios),
                "comment_count_average": _safe_average(comment_counts),
            }

        export_payload["metadata"] = dataset.metadata

        return json.dumps(export_payload, ensure_ascii=False)


class RedditDatasetLookupTool(BaseTool):
    name: str = "reddit_dataset_lookup"
    description: str = (
        "Retrieve specific posts from a stored dataset using post_ids or by applying a simple limit for sampling."
    )
    args_schema: Type[BaseModel] = RedditDatasetLookupArgs

    def _run(  # type: ignore[override]
        self,
        dataset_id: str,
        post_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
        include_metadata: bool = False,
    ) -> str:
        try:
            dataset = _DATASET_STORE.get(dataset_id)
        except ValueError as exc:
            return json.dumps(
                {"status": "error", "message": str(exc), "tool": self.name},
                ensure_ascii=False,
            )

        working_items = dataset.iter_summaries()

        if post_ids:
            requested = {pid for pid in post_ids}
            working_items = [item for item in working_items if str(item.get("post_id")) in requested]
        elif limit is not None:
            working_items = working_items[:limit]

        payload: Dict[str, Any] = {
            "status": "success",
            "tool": self.name,
            "dataset_id": dataset_id,
            "item_count": len(working_items),
            "items": working_items,
        }
        if include_metadata:
            payload["metadata"] = dataset.metadata

        return json.dumps(payload, ensure_ascii=False)


class ContentExplorerTool(BaseTool):
    name: str = "content_explorer"
    description: str = (
        "Explore stored Reddit datasets at varying levels of depth. Supports summary inspection, "
        "normalised post retrieval, comment tree expansion and raw payload access on demand."
    )
    args_schema: Type[BaseModel] = ContentExplorerArgs

    def _select_pointers(
        self,
        dataset: _StoredDataset,
        post_ids: Optional[Sequence[str]],
        limit: Optional[int],
    ) -> List[str]:
        if post_ids:
            ordered: List[str] = []
            for post_id in post_ids:
                pointer = dataset.lookup_pointer(post_id)
                if pointer:
                    ordered.append(pointer)
            return ordered
        pointers = dataset.pointer_sequence()
        if limit is not None:
            return pointers[:limit]
        return pointers

    def _run(  # type: ignore[override]
        self,
        dataset_id: str,
        post_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
        data_level: str = "summary",
        include_dataset_metadata: bool = False,
        extra_fields: Optional[Sequence[str]] = None,
        comment_filters: Optional[List[FilterCondition]] = None,
        comment_sort_by: Optional[str] = None,
        comment_limit: Optional[int] = None,
    ) -> str:
        try:
            dataset = _DATASET_STORE.get(dataset_id)
        except ValueError as exc:
            return json.dumps(
                {"status": "error", "message": str(exc), "tool": self.name},
                ensure_ascii=False,
            )

        pointers = self._select_pointers(dataset, post_ids, limit)
        extra_fields_tuple: Tuple[str, ...] = tuple(sorted(extra_fields or []))

        items: List[Dict[str, Any]]
        selected_post_ids: List[str] = []

        if data_level == "summary":
            items = dataset.summaries_for_pointers(pointers)
            selected_post_ids = [str(item.get("post_id")) for item in items if item.get("post_id") is not None]
        else:
            items = []
            for pointer in pointers:
                summary = dataset.summary_for_pointer(pointer)
                raw_item = dataset.raw_for_pointer(pointer)
                if summary is None or raw_item is None:
                    continue
                if summary.get("post_id") is not None:
                    selected_post_ids.append(str(summary["post_id"]))

                if data_level == "raw":
                    items.append(
                        {
                            "summary": summary,
                            "raw_pointer": summary.get("raw_pointer"),
                            "raw": raw_item,
                        }
                    )
                    continue

                cached = dataset.get_cached_normalised(pointer, extra_fields_tuple)
                if cached is None:
                    cached = _normalise_post(
                        summary,
                        raw_item,
                        extra_fields=extra_fields_tuple,
                    )
                    dataset.cache_normalised(pointer, extra_fields_tuple, cached)
                base_payload = copy.deepcopy(cached)

                if data_level == "full_comments":
                    comment_tree = _retrieve_comment_tree(dataset, pointer, raw_item)
                    filtered_comments = _filter_comment_list(comment_tree, comment_filters)
                    filtered_comments = _sort_and_limit_comments(
                        filtered_comments,
                        sort_by=comment_sort_by,
                        limit=comment_limit,
                    )
                    base_payload["comments"] = filtered_comments
                    total_count = 0
                    for comment in filtered_comments:
                        total_count += 1 + _count_comment_tree(comment.get("replies"))
                    base_payload["comment_summary"] = {
                        "top_level_count": len(filtered_comments),
                        "total_count": total_count,
                        "filters_applied": [f.model_dump() for f in comment_filters] if comment_filters else None,
                        "sort_by": comment_sort_by,
                        "limit": comment_limit,
                    }
                items.append(base_payload)

        payload: Dict[str, Any] = {
            "status": "success",
            "tool": self.name,
            "dataset_id": dataset_id,
            "data_level": data_level,
            "item_count": len(items),
            "items": items,
            "selected_post_ids": selected_post_ids,
        }

        if data_level == "full_comments":
            payload["comment_request"] = {
                "filters": [f.model_dump() for f in comment_filters] if comment_filters else None,
                "sort_by": comment_sort_by,
                "limit": comment_limit,
            }

        if include_dataset_metadata:
            payload["metadata"] = dataset.metadata

        return json.dumps(payload, ensure_ascii=False)


class MediaAnalyzerTool(BaseTool):
    name: str = "media_analyzer"
    description: str = (
        "Download visual media referenced in Reddit posts and generate an analytical description using the Gemini "
        "multimodal API."
    )
    args_schema: Type[BaseModel] = MediaAnalyzerArgs

    def _run(  # type: ignore[override]
        self,
        url: str,
        prompt: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        download_timeout: int = 15,
    ) -> str:
        try:
            response = requests.get(url, timeout=download_timeout)
        except requests.RequestException as exc:
            return json.dumps(
                {
                    "status": "error",
                    "tool": self.name,
                    "message": f"Failed to download media: {exc}",
                    "url": url,
                },
                ensure_ascii=False,
            )

        if response.status_code >= 400:
            return json.dumps(
                {
                    "status": "error",
                    "tool": self.name,
                    "message": f"Media request returned status {response.status_code}",
                    "url": url,
                },
                ensure_ascii=False,
            )

        content_type = response.headers.get("Content-Type", "application/octet-stream")
        media_bytes = response.content

        module_spec = importlib.util.find_spec("google.generativeai")
        if module_spec is None:
            return json.dumps(
                {
                    "status": "error",
                    "tool": self.name,
                    "message": "google.generativeai is not installed in this environment.",
                    "url": url,
                },
                ensure_ascii=False,
            )

        genai = importlib.import_module("google.generativeai")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return json.dumps(
                {
                    "status": "error",
                    "tool": self.name,
                    "message": "GEMINI_API_KEY environment variable is not set.",
                    "url": url,
                },
                ensure_ascii=False,
            )

        genai.configure(api_key=api_key)
        default_prompt = prompt or "Provide a concise creative brief describing the visual content, notable objects, mood and any brand-relevant cues present in this media."

        try:
            model_client = genai.GenerativeModel(model)
            generation = model_client.generate_content(
                [
                    default_prompt,
                    {"mime_type": content_type, "data": media_bytes},
                ]
            )
        except Exception as exc:  # pragma: no cover - external dependency
            return json.dumps(
                {
                    "status": "error",
                    "tool": self.name,
                    "message": f"Gemini analysis failed: {exc}",
                    "url": url,
                },
                ensure_ascii=False,
            )

        analysis_text: Optional[str] = None
        if hasattr(generation, "text"):
            analysis_text = getattr(generation, "text")
        elif hasattr(generation, "candidates"):
            candidates = getattr(generation, "candidates")
            if candidates:
                first = candidates[0]
                if isinstance(first, Mapping) and "content" in first:
                    analysis_text = str(first["content"])
                elif hasattr(first, "content"):
                    analysis_text = str(getattr(first, "content"))
        if analysis_text is None:
            analysis_text = str(generation)

        return json.dumps(
            {
                "status": "success",
                "tool": self.name,
                "url": url,
                "model": model,
                "prompt": default_prompt,
                "content_type": content_type,
                "content_length": len(media_bytes),
                "analysis": analysis_text,
            },
            ensure_ascii=False,
        )


reddit_scrape_locator_tool = RedditScrapeLocatorTool()
reddit_scrape_loader_tool = RedditScrapeLoaderTool()
reddit_dataset_filter_tool = RedditDatasetFilterTool()
reddit_dataset_export_tool = RedditDatasetExportTool()
reddit_dataset_lookup_tool = RedditDatasetLookupTool()
content_explorer_tool = ContentExplorerTool()
media_analyzer_tool = MediaAnalyzerTool()

__all__ = [
    "reddit_scrape_locator_tool",
    "reddit_scrape_loader_tool",
    "reddit_dataset_filter_tool",
    "reddit_dataset_export_tool",
    "reddit_dataset_lookup_tool",
    "content_explorer_tool",
    "media_analyzer_tool",
]
