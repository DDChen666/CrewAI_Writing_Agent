"""Command line entry-point for running the X and Reddit scrapers."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict

from scrapers.reddit.fallback_scraper import scrape_reddit_via_pullpush
from scrapers.reddit.main_scraper import fetch_subreddit_posts
from scrapers.x.fallback_scraper import scrape_x_via_nitter
from scrapers.x.main_scraper import scrape_x_via_snscrape


CONFIG_PATH = Path(__file__).with_name("scraper.json")


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def ensure_output_path(root: Path, platform: str) -> Path:
    today = dt.datetime.utcnow().strftime("%Y%m%d")
    timestamp = dt.datetime.utcnow().strftime("%Y%m%d%H%M")
    directory = root / today
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / f"{timestamp}_{platform}.json"
    return file_path


def write_output(path: Path, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


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
    except Exception:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run X or Reddit scraping workflows")
    parser.add_argument("platform", choices=["x", "reddit"], help="Target platform to scrape")
    parser.add_argument("target", help="Username (X) or subreddit name (Reddit)")
    parser.add_argument("--limit", type=int, help="Number of posts to retrieve")
    parser.add_argument("--skip-media", dest="skip_media", action="store_true", help="Skip posts that contain media")
    parser.add_argument("--include-media", dest="skip_media", action="store_false", help="Include posts with media")
    parser.set_defaults(skip_media=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    output_root = Path(config.get("output_root", "scraepr"))

    if args.platform == "x":
        payload = run_x_scraper(args, config)
    else:
        payload = run_reddit_scraper(args, config)

    output_path = ensure_output_path(output_root, args.platform)
    write_output(output_path, payload)
    print(f"Saved output to {output_path}")


if __name__ == "__main__":
    main()
