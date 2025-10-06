"""Primary scraper for Reddit using the official OAuth Data API."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Union

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


def _resolve_listing_path(subreddit: str, sort: str) -> str:
    listing_paths = {
        "hot": "hot",
        "new": "new",
        "top": "top",
        "rising": "rising",
        "controversial": "controversial",
        "best": "top",
    }
    return f"/r/{subreddit}/{listing_paths.get(sort, 'new')}"


def _collect_comment_nodes(
    things: List[Dict[str, Any]],
    *,
    seen: Optional[Set[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    comments: List[Dict[str, Any]] = []
    mores: List[Dict[str, Any]] = []
    if seen is None:
        seen = set()

    for thing in things:
        kind = thing.get("kind")
        data = thing.get("data", {})
        if kind == "t1":
            name = data.get("name")
            if name and name not in seen:
                seen.add(name)
                comments.append(data)
            replies = data.get("replies")
            if isinstance(replies, dict):
                child_things = replies.get("data", {}).get("children", [])
                child_comments, child_mores = _collect_comment_nodes(child_things, seen=seen)
                comments.extend(child_comments)
                mores.extend(child_mores)
        elif kind == "more":
            mores.append(data)

    return comments, mores


def _expand_more_children(
    client: RedditOAuthClient,
    link_fullname: str,
    pending_mores: List[Dict[str, Any]],
    *,
    timeout: int,
    seen: Set[str],
) -> List[Dict[str, Any]]:
    expanded: List[Dict[str, Any]] = []
    queue: List[Dict[str, Any]] = list(pending_mores)

    while queue:
        current = queue.pop(0)
        children_ids = [cid for cid in current.get("children", []) if cid]
        if not children_ids:
            continue

        while children_ids:
            batch = children_ids[:50]
            children_ids = children_ids[50:]
            payload = client.post(
                "/api/morechildren",
                data={
                    "api_type": "json",
                    "link_id": link_fullname,
                    "children": ",".join(batch),
                    "raw_json": 1,
                },
                timeout=timeout,
            )
            things = payload.get("json", {}).get("data", {}).get("things", [])
            child_comments, child_mores = _collect_comment_nodes(things, seen=seen)
            expanded.extend(child_comments)
            queue.extend(child_mores)

    return expanded


def _format_comment_node(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": data.get("id"),
        "author": data.get("author"),
        "body": data.get("body"),
        "score": data.get("score"),
        "created_utc": data.get("created_utc"),
        "replies": [],
    }


def _build_comment_tree(
    comment_nodes: List[Dict[str, Any]],
    *,
    link_fullname: str,
) -> List[Dict[str, Any]]:
    node_by_name: Dict[str, Dict[str, Any]] = {}
    children_by_parent: Dict[str, List[str]] = {}

    for data in comment_nodes:
        name = data.get("name")
        if not name:
            continue
        node_by_name[name] = _format_comment_node(data)
        parent_id = data.get("parent_id")
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(name)

    def _attach(name: str) -> Optional[Dict[str, Any]]:
        node = node_by_name.get(name)
        if node is None:
            return None
        child_names = children_by_parent.get(name, [])
        for child_name in child_names:
            child_node = _attach(child_name)
            if child_node is not None:
                node["replies"].append(child_node)
        return node

    roots: List[Dict[str, Any]] = []
    for child_name in children_by_parent.get(link_fullname, []):
        child_node = _attach(child_name)
        if child_node is not None:
            roots.append(child_node)

    return roots


def _fetch_comments(
    client: RedditOAuthClient,
    permalink: str,
    *,
    depth: Union[int, Literal["all"]],
    timeout: int,
) -> List[Dict[str, Any]]:
    if not permalink or depth == 0:
        return []

    endpoint = f"{permalink}.json" if permalink.startswith("/r/") else permalink
    params: Dict[str, Any] = {"limit": 100, "raw_json": 1}
    if isinstance(depth, int):
        params["depth"] = depth
    else:
        params["depth"] = 10

    payload = client.get(endpoint, params=params, timeout=timeout)
    if not isinstance(payload, list) or len(payload) < 2:
        return []

    post_listing = payload[0].get("data", {}).get("children", [])
    post_data = post_listing[0].get("data", {}) if post_listing else {}
    link_fullname = post_data.get("name", "")

    comment_listing = payload[1].get("data", {}).get("children", [])
    seen: Set[str] = set()
    comment_nodes, mores = _collect_comment_nodes(comment_listing, seen=seen)

    if depth == "all" and link_fullname:
        expanded_nodes = _expand_more_children(
            client,
            link_fullname,
            mores,
            timeout=timeout,
            seen=seen,
        )
        comment_nodes.extend(expanded_nodes)

    return _build_comment_tree(comment_nodes, link_fullname=link_fullname)


def fetch_subreddit_posts(
    subreddit: str,
    limit: int = 50,
    skip_media: bool = False,
    comment_depth: Union[int, Literal["all"]] = 2,
    timeout: int = 10,
    *,
    sort: str = "new",
    time_filter: Optional[str] = None,
    client: Optional[RedditOAuthClient] = None,
) -> Dict[str, Any]:
    """Fetch posts from a subreddit using the official OAuth API."""

    oauth_client = client or RedditOAuthClient(timeout=timeout)

    posts: List[Dict[str, Any]] = []
    after: Optional[str] = None

    normalized_sort = "top" if sort == "best" else sort
    listing_endpoint = _resolve_listing_path(subreddit, normalized_sort)

    while len(posts) < limit:
        params: Dict[str, Any] = {
            "limit": min(100, limit - len(posts)),
            "raw_json": 1,
        }
        if normalized_sort == "top" and time_filter:
            params["t"] = time_filter
        if after:
            params["after"] = after

        listing = oauth_client.get(listing_endpoint, params=params, timeout=timeout)
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
        "parameters": {
            "limit": limit,
            "sort": normalized_sort,
            "time_filter": time_filter,
            "comment_depth": comment_depth,
            "skip_media": skip_media,
        },
    }
