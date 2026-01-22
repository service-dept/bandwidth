"""Main entry point for bandwidth aggregator."""

import asyncio
from pathlib import Path

from .deduplicator import deduplicate, sort_by_date, take_top
from .fetcher import fetch_all_feeds
from .generator import generate_site
from .parser import parse_all_feeds
from .scraper import fetch_all_articles


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def main() -> None:
    """Run the aggregator pipeline."""
    root = get_project_root()

    sources_path = root / "config" / "sources.yaml"
    templates_path = root / "templates"
    static_path = root / "static"
    output_path = root / "output"

    print("bandwidth aggregator")
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

    # Fetch content and filter out empty articles, maintaining 25 stories
    print("\n5. Fetching article content...")
    final_stories = []
    batch_start = 0
    batch_size = 30  # Fetch extra to account for failures

    while len(final_stories) < 25 and batch_start < len(stories):
        batch = stories[batch_start : batch_start + batch_size]
        batch_with_content = asyncio.run(fetch_all_articles(batch))

        for story in batch_with_content:
            if story.content:
                final_stories.append(story)
                if len(final_stories) >= 25:
                    break

        batch_start += batch_size

    stories = final_stories
    print(f"  Selected: {len(stories)} stories with content")

    # Generate site
    print("\n6. Generating site...")
    generate_site(
        stories=stories,
        templates_path=str(templates_path),
        static_path=str(static_path),
        output_path=str(output_path),
        sources_path=str(sources_path),
    )

    print("\n" + "=" * 40)
    print("Done!")


if __name__ == "__main__":
    main()
