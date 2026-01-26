"""Async RSS feed fetcher."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import yaml

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class FeedResult:
    """Result of fetching a single feed."""

    name: str
    url: str
    content: str | None
    error: str | None = None


async def fetch_feed(client: httpx.AsyncClient, name: str, url: str) -> FeedResult:
    """Fetch a single RSS feed."""
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return FeedResult(name=name, url=url, content=response.text)
    except httpx.TimeoutException:
        return FeedResult(name=name, url=url, content=None, error="Timeout")
    except httpx.HTTPStatusError as e:
        return FeedResult(name=name, url=url, content=None, error=f"HTTP {e.response.status_code}")
    except Exception as e:
        return FeedResult(name=name, url=url, content=None, error=str(e))


async def fetch_all_feeds(sources_path: str) -> list[FeedResult]:
    """Fetch all RSS feeds from sources config."""
    with open(sources_path) as f:
        config = yaml.safe_load(f)

    sources = config.get("sources", [])

    # TODO: Validate required fields (name, url) to avoid KeyError crashes
    async with httpx.AsyncClient(timeout=5.0, headers={"User-Agent": USER_AGENT}) as client:
        tasks = [
            fetch_feed(client, source["name"], source["url"])
            for source in sources
            if source.get("type") in ("rss", "atom")  # atom kept for future use
        ]
        results = await asyncio.gather(*tasks)

    # Log results
    for result in results:
        if result.error:
            print(f"  [FAIL] {result.name}: {result.error}")
        else:
            print(f"  [OK]   {result.name}")

    return list(results)
