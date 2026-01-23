"""Parse RSS feeds into Story objects."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import feedparser

from .fetcher import FeedResult


@dataclass
class Story:
    """A single news story."""

    id: str
    title: str
    summary: str
    source: str
    source_url: str
    published: datetime
    fetched: datetime
    content: str = ""


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate(text: str, max_length: int = 280) -> str:
    """Truncate text to max length, ending at word boundary."""
    if len(text) <= max_length:
        return text
    truncated = text[: max_length - 3]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."


def parse_date(entry: dict[str, Any]) -> datetime:
    """Parse publication date from feed entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def generate_id(url: str) -> str:
    """Generate a short ID from URL hash."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def parse_feed(feed_result: FeedResult) -> list[Story]:
    """Parse a single feed result into stories."""
    if not feed_result.content:
        return []

    now = datetime.now(timezone.utc)
    stories = []

    feed = feedparser.parse(feed_result.content)

    for entry in feed.entries:
        url = entry.get("link", "")
        if not url:
            continue

        title = strip_html(entry.get("title", "Untitled"))
        if not title:
            continue

        summary = entry.get("summary", "") or entry.get("description", "")
        summary = strip_html(summary)
        summary = truncate(summary)

        story = Story(
            id=generate_id(url),
            title=title,
            summary=summary,
            source=feed_result.name,
            source_url=url,
            published=parse_date(entry),
            fetched=now,
        )
        stories.append(story)

    return stories


def parse_all_feeds(feed_results: list[FeedResult]) -> list[Story]:
    """Parse all feed results into stories."""
    all_stories = []
    for result in feed_results:
        stories = parse_feed(result)
        all_stories.extend(stories)
        print(f"  Parsed {len(stories)} stories from {result.name}")
    return all_stories
