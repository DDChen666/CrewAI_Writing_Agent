"""Primary scraper logic for X (formerly Twitter) using snscrape."""
from __future__ import annotations

import dataclasses
import datetime as dt
import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import snscrape


def _load_twitter_module():
    if "snscrape.modules.twitter" in sys.modules:
        return sys.modules["snscrape.modules.twitter"]

    modules_pkg = sys.modules.get("snscrape.modules")
    modules_path = Path(snscrape.__file__).parent / "modules"
    if modules_pkg is None:
        modules_pkg = types.ModuleType("snscrape.modules")
        modules_pkg.__path__ = [str(modules_path)]  # type: ignore[attr-defined]
        sys.modules["snscrape.modules"] = modules_pkg

    spec = importlib.util.spec_from_file_location(
        "snscrape.modules.twitter",
        modules_path / "twitter.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load snscrape.modules.twitter")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "snscrape.modules"
    sys.modules["snscrape.modules.twitter"] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


twitter = _load_twitter_module()


@dataclasses.dataclass
class MediaAsset:
    url: str
    type: str
    preview_url: Optional[str] = None


@dataclasses.dataclass
class ThreadEntry:
    id: int
    url: str
    content: str
    created_at: str
    author: Optional[str]
    like_count: Optional[int]
    reply_count: Optional[int]
    retweet_count: Optional[int]


@dataclasses.dataclass
class TweetRecord:
    id: int
    url: str
    content: str
    created_at: str
    author: Optional[str]
    like_count: Optional[int]
    reply_count: Optional[int]
    retweet_count: Optional[int]
    quote_count: Optional[int]
    lang: Optional[str]
    conversation_id: Optional[int]
    in_reply_to_tweet_id: Optional[int]
    thread: List[ThreadEntry]
    media: List[MediaAsset]


class XSnscrapeClient:
    """High level wrapper around snscrape for X user scraping."""

    def __init__(self, max_thread_items: int = 50) -> None:
        self.max_thread_items = max_thread_items
        self._logger = logging.getLogger(self.__class__.__name__)

    def fetch_user_tweets(
        self,
        username: str,
        limit: int = 50,
        skip_media: bool = False,
    ) -> List[TweetRecord]:
        scraper = twitter.TwitterUserScraper(username)
        tweets: List[TweetRecord] = []

        for tweet in scraper.get_items():
            if skip_media and self._tweet_has_media(tweet):
                continue

            tweets.append(self._build_record(tweet, skip_media=skip_media))
            if len(tweets) >= limit:
                break

        return tweets

    def _tweet_has_media(self, tweet: "twitter.Tweet") -> bool:
        if not tweet.media:
            return False
        return any(media for media in tweet.media)

    def _build_record(
        self,
        tweet: "twitter.Tweet",
        skip_media: bool = False,
    ) -> TweetRecord:
        media_assets = []
        if tweet.media and not skip_media:
            media_assets = [
                MediaAsset(
                    url=getattr(media, "fullUrl", None) or getattr(media, "url", ""),
                    type=media.__class__.__name__,
                    preview_url=getattr(media, "previewUrl", None),
                )
                for media in tweet.media
            ]

        thread_items = self._fetch_thread(tweet)

        return TweetRecord(
            id=tweet.id,
            url=tweet.url,
            content=tweet.rawContent,
            created_at=tweet.date.isoformat(),
            author=tweet.user.username if tweet.user else None,
            like_count=tweet.likeCount,
            reply_count=tweet.replyCount,
            retweet_count=tweet.retweetCount,
            quote_count=tweet.quoteCount,
            lang=tweet.lang,
            conversation_id=tweet.conversationId,
            in_reply_to_tweet_id=tweet.inReplyToTweetId,
            thread=thread_items,
            media=media_assets,
        )

    def _fetch_thread(self, tweet: "twitter.Tweet") -> List[ThreadEntry]:
        if tweet.conversationId is None:
            return []

        thread_scraper = twitter.TwitterTweetScraper(tweet.conversationId)
        thread_entries: List[ThreadEntry] = []
        for idx, thread_tweet in enumerate(thread_scraper.get_items()):
            if idx >= self.max_thread_items:
                break

            thread_entries.append(
                ThreadEntry(
                    id=thread_tweet.id,
                    url=thread_tweet.url,
                    content=thread_tweet.rawContent,
                    created_at=thread_tweet.date.isoformat(),
                    author=thread_tweet.user.username if thread_tweet.user else None,
                    like_count=thread_tweet.likeCount,
                    reply_count=thread_tweet.replyCount,
                    retweet_count=thread_tweet.retweetCount,
                )
            )
        return thread_entries


def serialize_tweets(tweets: Iterable[TweetRecord]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for tweet in tweets:
        serialized.append(
            {
                "id": tweet.id,
                "url": tweet.url,
                "content": tweet.content,
                "created_at": tweet.created_at,
                "author": tweet.author,
                "statistics": {
                    "likes": tweet.like_count,
                    "replies": tweet.reply_count,
                    "retweets": tweet.retweet_count,
                    "quotes": tweet.quote_count,
                },
                "language": tweet.lang,
                "conversation_id": tweet.conversation_id,
                "in_reply_to_tweet_id": tweet.in_reply_to_tweet_id,
                "thread": [
                    {
                        "id": item.id,
                        "url": item.url,
                        "content": item.content,
                        "created_at": item.created_at,
                        "author": item.author,
                        "statistics": {
                            "likes": item.like_count,
                            "replies": item.reply_count,
                            "retweets": item.retweet_count,
                        },
                    }
                    for item in tweet.thread
                ],
                "media": [
                    {
                        "type": media.type,
                        "url": media.url,
                        "preview_url": media.preview_url,
                    }
                    for media in tweet.media
                ],
            }
        )
    return serialized


def scrape_x_via_snscrape(
    username: str,
    limit: int,
    skip_media: bool,
    thread_limit: int = 50,
) -> Dict[str, Any]:
    client = XSnscrapeClient(max_thread_items=thread_limit)
    tweets = client.fetch_user_tweets(username=username, limit=limit, skip_media=skip_media)
    return {
        "platform": "x",
        "account": username,
        "scraped_at": dt.datetime.utcnow().isoformat(),
        "items": serialize_tweets(tweets),
        "source": "snscrape",
    }
