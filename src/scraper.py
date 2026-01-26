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


def load_source_config() -> dict[str, dict]:
    """Load source-specific config from sources.yaml."""
    global _source_patterns
    if _source_patterns is not None:
        return _source_patterns

    config_path = Path(__file__).parent.parent / "config" / "sources.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    _source_patterns = {}
    for source in config.get("sources", []):
        source_config = {}

        # Content start pattern (trim leading cruft)
        if "content_start_pattern" in source:
            source_config["start_pattern"] = source["content_start_pattern"]

        # Content end patterns (trim trailing cruft)
        if "content_end_patterns" in source:
            source_config["patterns"] = source["content_end_patterns"]
        elif "content_end_pattern" in source:
            source_config["patterns"] = [source["content_end_pattern"]]

        # Extraction mode (precision or recall)
        if "extraction_mode" in source:
            source_config["extraction_mode"] = source["extraction_mode"]

        if source_config:
            _source_patterns[source["name"]] = source_config

    return _source_patterns


def clean_content(html: str, source_name: str | None = None) -> str:
    """Remove promotional content from article HTML using source-specific patterns."""
    if not html:
        return html

    source_cfg = {}
    if source_name:
        config = load_source_config()
        source_cfg = config.get(source_name, {})

    # Handle content_start_pattern - trim everything before and including the LAST match
    start_pattern = source_cfg.get("start_pattern")
    if start_pattern:
        matches = list(re.finditer(start_pattern, html, re.IGNORECASE))
        if matches:
            last_match = matches[-1]
            # Find the next paragraph after the last match
            next_p = html.find('<p', last_match.end())
            if next_p > 0:
                html = html[next_p:]
            else:
                html = html[last_match.end():]
            html = html.strip()

    # Handle content_end_pattern(s) - trim everything after the match
    end_patterns = source_cfg.get("patterns", [])
    if end_patterns:
        earliest_pos = len(html)
        for pattern in end_patterns:
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

    # Check for source-specific extraction mode
    use_recall = False
    if source_name:
        config = load_source_config()
        source_cfg = config.get(source_name, {})
        use_recall = source_cfg.get("extraction_mode") == "recall"

    content = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
        favor_precision=not use_recall,
        favor_recall=use_recall,
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
