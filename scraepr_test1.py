"""Command line entry-point for running the social media scrapers."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List

import logging
from scrapers.facebook import (
    scrape_facebook_via_facebook_scraper,
    scrape_facebook_via_rsshub,
)
from scrapers.reddit.fallback_scraper import scrape_reddit_via_pullpush
from scrapers.reddit.main_scraper import fetch_subreddit_posts
from scrapers.threads import scrape_threads_via_rsshub, scrape_threads_via_threadsnet
from scrapers.x.fallback_scraper import scrape_x_via_nitter
from scrapers.x.main_scraper import scrape_x_via_snscrape


CONFIG_PATH = Path(__file__).with_name("scraper.json")


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def ensure_output_path(root: Path, platform: str) -> Path:
    now = dt.datetime.now(dt.UTC)
    today = now.strftime("%Y%m%d")
    timestamp = now.strftime("%Y%m%d%H%M")
    directory = root / today
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / f"{timestamp}_{platform}.json"
    return file_path


def write_output(path: Path, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


logger = logging.getLogger(__name__)


def run_x_scraper(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    platform_conf = config.get("x", {})
    limit = args.limit or platform_conf.get("max_posts", 50)
    skip_media = args.skip_media if args.skip_media is not None else platform_conf.get("skip_media_posts", True)
    thread_limit = platform_conf.get("thread_depth_limit", 50)

    try:
        return scrape_x_via_snscrape(
            username=args.target,
            limit=limit,
            skip_media=skip_media,
            thread_limit=thread_limit,
        )
    except Exception as exc:
        logger.warning("snscrape failed for %s, falling back to Nitter: %s", args.target, exc)
        instances = platform_conf.get("nitter_instances", [])
        timeout = platform_conf.get("request_timeout", 10)
        retries = platform_conf.get("max_retries", 2)
        return scrape_x_via_nitter(
            username=args.target,
            instances=instances,
            limit=limit,
            skip_media=skip_media,
            timeout=timeout,
            max_retries=retries,
        )


def run_reddit_scraper(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    platform_conf = config.get("reddit", {})
    limit = args.limit or platform_conf.get("max_posts", 50)
    skip_media = args.skip_media if args.skip_media is not None else platform_conf.get("skip_media_posts", True)
    comment_depth = platform_conf.get("comment_depth", 2)
    timeout = platform_conf.get("request_timeout", 10)

    try:
        return fetch_subreddit_posts(
            subreddit=args.target,
            limit=limit,
            skip_media=skip_media,
            comment_depth=comment_depth,
            timeout=timeout,
        )
    except Exception:
        base_url = platform_conf.get("pullpush_base")
        retries = platform_conf.get("max_retries", 2)
        return scrape_reddit_via_pullpush(
            subreddit=args.target,
            base_url=base_url,
            limit=limit,
            skip_media=skip_media,
            timeout=timeout,
            max_retries=retries,
        )


def run_facebook_scraper(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    platform_conf = config.get("facebook", {})
    limit = args.limit or platform_conf.get("max_posts", 25)
    include_comments = platform_conf.get("include_comments", True)
    include_media = platform_conf.get("include_media", True)
    timeout = platform_conf.get("request_timeout", 15)

    fetch_media = include_media
    if args.skip_media is not None:
        fetch_media = not args.skip_media

    try:
        return scrape_facebook_via_facebook_scraper(
            target_url=args.target,
            limit=limit,
            fetch_comments=include_comments,
            fetch_media=fetch_media,
            timeout=timeout,
        )
    except Exception as exc:
        logger.warning("facebook-scraper failed for %s, falling back to RSSHub: %s", args.target, exc)
        return scrape_facebook_via_rsshub(
            target_url=args.target,
            limit=limit,
            timeout=timeout,
        )


def run_threads_scraper(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    platform_conf = config.get("threads", {})
    limit = args.limit or platform_conf.get("max_posts", 25)
    timeout = platform_conf.get("request_timeout", 15)

    try:
        return scrape_threads_via_threadsnet(
            target_url=args.target,
            limit=limit,
            timeout=timeout,
        )
    except Exception as exc:
        logger.warning("threads.net scraping failed for %s, falling back to RSSHub: %s", args.target, exc)
        return scrape_threads_via_rsshub(
            target_url=args.target,
            limit=limit,
            timeout=timeout,
        )


TEST_SCENARIOS = [
    {
        "platform": "facebook",
        "target": "https://www.facebook.com/groups/1895839270947969",
        "description": "Facebook public group: 1895839270947969",
    },
    {
        "platform": "facebook",
        "target": "https://www.facebook.com/intleconobserve",
        "description": "Facebook page: intleconobserve",
    },
    {
        "platform": "threads",
        "target": "https://www.threads.com/@aiposthub",
        "description": "Threads profile: @aiposthub",
    },
    {
        "platform": "threads",
        "target": "https://www.threads.com/search?q=Vibe%20Coding&serp_type=tags&tag_id=18386070271105161",
        "description": "Threads hashtag search: Vibe Coding",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run social media scraping workflows")
    parser.add_argument(
        "platform",
        choices=["x", "reddit", "facebook", "threads", "tests"],
        help="Target platform to scrape",
    )
    parser.add_argument("target", nargs="?", help="Identifier for the requested platform")
    parser.add_argument("--limit", type=int, help="Number of posts to retrieve")
    parser.add_argument("--skip-media", dest="skip_media", action="store_true", help="Skip posts that contain media")
    parser.add_argument("--include-media", dest="skip_media", action="store_false", help="Include posts with media")
    parser.set_defaults(skip_media=None)
    return parser.parse_args()


def run_smoke_tests(config: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Running smoke tests for preset Facebook and Threads targets")
    output_root = Path(config.get("output_root", "scraepr"))

    summary: List[Dict[str, Any]] = []
    for scenario in TEST_SCENARIOS:
        namespace = argparse.Namespace(target=scenario["target"], limit=None, skip_media=None)
        platform = scenario["platform"]
        description = scenario["description"]
        try:
            if platform == "facebook":
                payload = run_facebook_scraper(namespace, config)
            elif platform == "threads":
                payload = run_threads_scraper(namespace, config)
            else:
                raise ValueError(f"Unsupported test platform: {platform}")

            payload["scenario"] = description
            output_path = ensure_output_path(output_root, f"{platform}_test")
            write_output(output_path, payload)
            summary.append(
                {
                    "platform": platform,
                    "description": description,
                    "status": "ok",
                    "scraper": payload.get("scraper"),
                    "post_count": payload.get("post_count"),
                    "output_file": str(output_path),
                }
            )
            print(f"[OK] {description} → {output_path} ({payload.get('post_count')} posts)")
        except Exception as exc:  # pragma: no cover - network dependent
            summary.append(
                {
                    "platform": platform,
                    "description": description,
                    "status": "error",
                    "error": str(exc),
                }
            )
            print(f"[ERROR] {description}: {exc}")

    aggregate = {
        "fetched_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "results": summary,
    }
    aggregate_path = ensure_output_path(output_root, "smoke_tests")
    write_output(aggregate_path, aggregate)
    print(f"Saved aggregate results to {aggregate_path}")
    return aggregate


def main() -> None:
    args = parse_args()
    config = load_config()
    output_root = Path(config.get("output_root", "scraepr"))

    logging.basicConfig(level=logging.INFO)

    if args.platform == "tests":
        run_smoke_tests(config)
        return

    if args.target is None:
        raise SystemExit("A target identifier must be supplied for this platform")

    if args.platform == "x":
        payload = run_x_scraper(args, config)
    elif args.platform == "reddit":
        payload = run_reddit_scraper(args, config)
    elif args.platform == "facebook":
        payload = run_facebook_scraper(args, config)
    elif args.platform == "threads":
        payload = run_threads_scraper(args, config)
    else:
        raise SystemExit(f"Unsupported platform: {args.platform}")

    output_path = ensure_output_path(output_root, args.platform)
    write_output(output_path, payload)
    print(f"Saved output to {output_path}")


if __name__ == "__main__":
    main()
