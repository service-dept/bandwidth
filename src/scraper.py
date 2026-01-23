"""Async article content scraper using trafilatura."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import httpx
import trafilatura

from .parser import Story


async def fetch_article_html(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch raw HTML from article URL."""
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text
    except Exception:
        return None


def extract_content(html: str) -> Optional[str]:
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
    import re
    content = re.sub(r'^<html>\s*<body>\s*', '', content)
    content = re.sub(r'\s*</body>\s*</html>\s*$', '', content)
    # Convert heading tags to paragraphs with class for easier styling
    content = re.sub(r'<h[1-6][^>]*>', '<p class="subheading">', content)
    content = re.sub(r'</h[1-6]>', '</p>', content)
    return content


async def fetch_article_content(
    client: httpx.AsyncClient,
    executor: ThreadPoolExecutor,
    story: Story,
) -> Optional[str]:
    """Fetch and extract article content for a single story."""
    try:
        html = await fetch_article_html(client, story.source_url)
        if not html:
            return None

        # Run trafilatura in thread pool (it's CPU-bound)
        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(executor, extract_content, html)
        return content
    except Exception:
        return None


async def fetch_all_articles(stories: List[Story]) -> List[Story]:
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
