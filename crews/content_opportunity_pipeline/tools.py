"""Tools supporting the Content Opportunity Pipeline."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, RootModel

# ---------------------------------------------------------------------------
# Dataset registry utilities
# ---------------------------------------------------------------------------


@dataclass
class _StoredDataset:
    """Internal representation of a dataset stored in memory."""

    items: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class _DatasetStore:
    """Lightweight in-memory dataset store used by the triage tools."""

    def __init__(self) -> None:
        self._datasets: Dict[str, _StoredDataset] = {}

    def store(self, items: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
        dataset_id = str(uuid.uuid4())
        self._datasets[dataset_id] = _StoredDataset(items=items, metadata=metadata)
        return dataset_id

    def get(self, dataset_id: str) -> _StoredDataset:
        try:
            return self._datasets[dataset_id]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unknown dataset_id: {dataset_id}") from exc

    def update(self, dataset_id: str, *, items: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> None:
        dataset = self.get(dataset_id)
        dataset.items = items
        if metadata:
            dataset.metadata.update(metadata)

    def summary(self, dataset_id: str) -> Dict[str, Any]:
        dataset = self.get(dataset_id)
        summary: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "item_count": len(dataset.items),
            "metadata": dataset.metadata,
        }
        return summary

    def drop(self, dataset_id: str) -> None:
        self._datasets.pop(dataset_id, None)


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


def _normalise_post(item: Dict[str, Any], extra_fields: Sequence[str]) -> Dict[str, Any]:
    """Produce a normalised dictionary for downstream agents."""

    normalised: Dict[str, Any] = {}
    for output_field, (source_field, _) in _DEFAULT_FIELD_MAPPING.items():
        value = _resolve_field(item, source_field)
        if output_field == "created_utc" and isinstance(value, (int, float)):
            normalised["created_utc"] = float(value)
            normalised["created_at_iso"] = datetime.utcfromtimestamp(float(value)).isoformat() + "Z"
        else:
            normalised[output_field] = value
    for field in extra_fields:
        if field in normalised:
            continue
        normalised[field] = _resolve_field(item, field)
    normalised["subreddit"] = _resolve_field(item, "subreddit")
    normalised["platform"] = "reddit"
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

    def _filter_item(self, item: Dict[str, Any], filters: Optional[List[FilterCondition]]) -> bool:
        if not filters:
            return True
        for rule in filters:
            candidate = item.get(rule.field)
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

        extra_fields: Sequence[str] = list(select_fields or [])
        combined_items: List[Dict[str, Any]] = []
        source_files: List[str] = []
        subreddits: List[str] = []

        for raw_path in file_paths:
            path = Path(raw_path)
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("platform") != "reddit":
                continue
            source_files.append(str(path.as_posix()))
            subreddit = payload.get("subreddit")
            if subreddit:
                subreddits.append(subreddit)
            for raw_item in payload.get("items", []):
                normalised = _normalise_post(raw_item, extra_fields)
                if drop_removed and isinstance(normalised.get("body"), str) and normalised["body"].lower() in {"[removed]", "[deleted]"}:
                    continue
                combined_items.append(normalised)

        if filters:
            filtered: List[Dict[str, Any]] = []
            for item in combined_items:
                if self._filter_item(item, filters):
                    filtered.append(item)
            combined_items = filtered

        if sort_by:
            combined_items.sort(key=lambda itm: itm.get(sort_by), reverse=descending)

        if max_items is not None:
            combined_items = combined_items[: max_items]

        dataset_metadata: Dict[str, Any] = {
            "source_files": source_files,
            "subreddits": sorted({sub for sub in subreddits if sub}),
            "fields": list(_DEFAULT_FIELD_MAPPING.keys()) + list(extra_fields),
            "total_items": len(combined_items),
        }
        dataset_id = _DATASET_STORE.store(combined_items, dataset_metadata)

        preview_items = combined_items[: min(len(combined_items), 5)]

        return json.dumps(
            {
                "status": "success",
                "tool": self.name,
                "dataset_id": dataset_id,
                "item_count": len(combined_items),
                "preview": preview_items,
                "metadata": dataset_metadata,
            },
            ensure_ascii=False,
        )


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

        working_items = list(dataset.items)

        if filters:
            filtered: List[Dict[str, Any]] = []
            for item in working_items:
                include = True
                for rule in filters:
                    candidate = item.get(rule.field)
                    if not _apply_condition(candidate, operator=rule.operator, expected=rule.value):
                        include = False
                        break
                if include:
                    filtered.append(item)
            working_items = filtered

        if sort_by:
            working_items.sort(key=lambda itm: itm.get(sort_by), reverse=descending)

        if limit is not None:
            working_items = working_items[:limit]

        new_metadata = dict(dataset.metadata)
        new_metadata["filtered_from"] = dataset_id
        new_metadata["total_items"] = len(working_items)
        new_dataset_id = _DATASET_STORE.store(working_items, new_metadata)

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

        items = list(dataset.items)
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

        working_items = list(dataset.items)

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


reddit_scrape_locator_tool = RedditScrapeLocatorTool()
reddit_scrape_loader_tool = RedditScrapeLoaderTool()
reddit_dataset_filter_tool = RedditDatasetFilterTool()
reddit_dataset_export_tool = RedditDatasetExportTool()
reddit_dataset_lookup_tool = RedditDatasetLookupTool()

__all__ = [
    "reddit_scrape_locator_tool",
    "reddit_scrape_loader_tool",
    "reddit_dataset_filter_tool",
    "reddit_dataset_export_tool",
    "reddit_dataset_lookup_tool",
]
