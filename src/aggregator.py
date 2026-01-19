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

    # Sort and take top 50
    print("\n4. Sorting and selecting top 50...")
    stories = sort_by_date(stories)
    stories = take_top(stories, 50)
    print(f"  Selected: {len(stories)} stories")

    # Fetch full article content
    print("\n5. Fetching article content...")
    stories = asyncio.run(fetch_all_articles(stories))

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
