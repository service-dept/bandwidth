"""Deduplicate stories by URL."""

from __future__ import annotations


from .parser import Story


def deduplicate(stories: list[Story]) -> list[Story]:
    """Remove duplicate stories based on URL hash (id)."""
    seen_ids: set[str] = set()
    unique_stories: list[Story] = []

    for story in stories:
        if story.id not in seen_ids:
            seen_ids.add(story.id)
            unique_stories.append(story)

    removed = len(stories) - len(unique_stories)
    if removed > 0:
        print(f"  Removed {removed} duplicate stories")

    return unique_stories


def sort_by_date(stories: list[Story]) -> list[Story]:
    """Sort stories by publication date, newest first."""
    return sorted(stories, key=lambda s: s.published, reverse=True)


def take_top(stories: list[Story], n: int = 25) -> list[Story]:
    """Return the top N stories (assumes already sorted by date)."""
    return stories[:n]
