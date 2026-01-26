"""Async article content scraper using trafilatura."""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import trafilatura
import yaml

from .parser import Story


# Cache for source patterns loaded from config
_source_patterns: dict[str, str] | None = None


def load_source_patterns() -> dict[str, list[str]]:
    """Load content_end_pattern mappings from sources.yaml."""
    global _source_patterns
    if _source_patterns is not None:
        return _source_patterns

    config_path = Path(__file__).parent.parent / "config" / "sources.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    _source_patterns = {}
    for source in config.get("sources", []):
        if "content_end_patterns" in source:
            # List of patterns
            _source_patterns[source["name"]] = source["content_end_patterns"]
        elif "content_end_pattern" in source:
            # Single pattern (backwards compatible)
            _source_patterns[source["name"]] = [source["content_end_pattern"]]

    return _source_patterns


def clean_content(html: str, source_name: str | None = None) -> str:
    """Remove promotional content from article HTML using source-specific patterns."""
    if not html:
        return html

    patterns = []
    if source_name:
        all_patterns = load_source_patterns()
        patterns = all_patterns.get(source_name, [])

    if not patterns:
        return html

    # Find earliest match across all patterns
    earliest_pos = len(html)
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match and match.start() < earliest_pos:
            earliest_pos = match.start()

    if earliest_pos < len(html):
        html = html[:earliest_pos]

        # Clean up: remove any incomplete trailing paragraph
        last_p_close = html.rfind('</p>')
        if last_p_close > 0:
            html = html[:last_p_close + 4]

        html = html.strip()

    return html


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def fetch_article_html(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch raw HTML from article URL."""
    try:
        response = await client.get(
            url,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        return response.text
    except Exception:
        return None


def extract_content(html: str, source_name: str | None = None) -> str | None:
    """Extract main article content from HTML using trafilatura."""
    if not html:
        return None
    content = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
        favor_precision=True,
        output_format="html",
    )
    if not content:
        return None
    # Strip outer html/body tags that trafilatura adds
    content = re.sub(r'^<html>\s*<body>\s*', '', content)
    content = re.sub(r'\s*</body>\s*</html>\s*$', '', content)
    # Convert heading tags to paragraphs with class for easier styling
    content = re.sub(r'<h[1-6][^>]*>', '<p class="subheading">', content)
    content = re.sub(r'</h[1-6]>', '</p>', content)
    # Remove promotional content using source-specific patterns
    content = clean_content(content, source_name)
    return content


async def fetch_article_content(
    client: httpx.AsyncClient,
    executor: ThreadPoolExecutor,
    story: Story,
) -> str | None:
    """Fetch and extract article content for a single story."""
    try:
        html = await fetch_article_html(client, story.source_url)
        if not html:
            return None

        # Run trafilatura in thread pool (it's CPU-bound)
        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(
            executor,
            lambda: extract_content(html, story.source),
        )
        return content
    except Exception:
        return None


async def fetch_all_articles(stories: list[Story]) -> list[Story]:
    """Fetch full article content for all stories."""
    # TODO: Add semaphore to limit concurrent connections and prevent memory spikes
    # Use thread pool for CPU-bound trafilatura extraction
    executor = ThreadPoolExecutor(max_workers=8)

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [
            fetch_article_content(client, executor, story)
            for story in stories
        ]
        contents = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to None
    contents = [None if isinstance(c, Exception) else c for c in contents]

    executor.shutdown(wait=False)

    # Update stories with content
    updated_stories = []
    success_count = 0
    for story, content in zip(stories, contents):
        if content:
            story.content = content
            success_count += 1
        else:
            story.content = ""
        updated_stories.append(story)

    print(f"  Fetched content for {success_count}/{len(stories)} articles")
    return updated_stories
