"""Export aggregated stories to sample_data.json format."""

import asyncio
import json
from pathlib import Path

import yaml

from src.aggregator import MAX_PER_SOURCE, MIN_CONTENT_LENGTH
from src.deduplicator import deduplicate, sort_by_date
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

    # Sort by date
    print("\n4. Sorting by date...")
    stories = sort_by_date(stories)

    # Fetch content and select top 25 with source diversity
    print("\n5. Fetching article content...")
    final_stories = []
    source_counts: dict[str, int] = {}
    batch_start = 0
    batch_size = 30

    while len(final_stories) < 30 and batch_start < len(stories):
        batch = stories[batch_start : batch_start + batch_size]
        batch_with_content = asyncio.run(fetch_all_articles(batch))

        for story in batch_with_content:
            if story.content and len(story.content) >= MIN_CONTENT_LENGTH:
                if source_counts.get(story.source, 0) >= MAX_PER_SOURCE:
                    continue
                source_counts[story.source] = source_counts.get(story.source, 0) + 1
                final_stories.append(story)
                if len(final_stories) >= 30:
                    break

        batch_start += batch_size

    stories = final_stories
    print(f"  Selected: {len(stories)} stories with content")

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
