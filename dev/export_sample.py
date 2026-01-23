"""Export aggregated stories to sample_data.json format."""

import asyncio
import json
from pathlib import Path

import yaml

from src.deduplicator import deduplicate, sort_by_date, take_top
from src.fetcher import fetch_all_feeds
from src.parser import parse_all_feeds
from src.scraper import fetch_all_articles


def main() -> None:
    """Export stories to sample_data.json."""
    dev_dir = Path(__file__).parent
    root = dev_dir.parent
    sources_path = root / "config" / "sources.yaml"
    output_path = dev_dir / "sample_data.json"

    print("Exporting to sample_data.json...")
    print("=" * 40)

    # Fetch feeds
    print("\n1. Fetching feeds...")
    feed_results = asyncio.run(fetch_all_feeds(str(sources_path)))

    # Parse stories
    print("\n2. Parsing stories...")
    stories = parse_all_feeds(feed_results)
    print(f"  Total: {len(stories)} stories")

    # Deduplicate
    print("\n3. Deduplicating...")
    stories = deduplicate(stories)
    print(f"  Unique: {len(stories)} stories")

    # Sort and take top 25
    print("\n4. Sorting and selecting top 25...")
    stories = sort_by_date(stories)
    stories = take_top(stories, 25)
    print(f"  Selected: {len(stories)} stories")

    # Fetch full article content
    print("\n5. Fetching article content...")
    stories = asyncio.run(fetch_all_articles(stories))

    # Load sources
    with open(sources_path) as f:
        sources_config = yaml.safe_load(f)

    # Convert to JSON format
    print("\n6. Converting to JSON...")
    stories_json = []
    for story in stories:
        stories_json.append({
            "id": story.id,
            "title": story.title,
            "url": story.source_url,
            "summary": story.summary,
            "source": story.source,
            "source_url": story.source_url,
            "published": story.published.isoformat(),
            "fetched": story.fetched.isoformat(),
            "content": story.content,
        })

    sources_json = [
        {"name": s["name"], "url": s.get("url", ""), "homepage": s.get("homepage", "")}
        for s in sources_config.get("sources", [])
    ]

    output_data = {
        "stories": stories_json,
        "sources": sources_json,
    }

    # Write to file
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nExported {len(stories_json)} stories to {output_path}")
    print("=" * 40)
    print("Done!")


if __name__ == "__main__":
    main()
