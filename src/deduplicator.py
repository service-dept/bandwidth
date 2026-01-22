"""Deduplicate stories by URL."""

from __future__ import annotations

from typing import List, Set

from .parser import Story


def deduplicate(stories: List[Story]) -> List[Story]:
    """Remove duplicate stories based on URL hash (id)."""
    seen_ids: Set[str] = set()
    unique_stories: List[Story] = []

    for story in stories:
        if story.id not in seen_ids:
            seen_ids.add(story.id)
            unique_stories.append(story)

    removed = len(stories) - len(unique_stories)
    if removed > 0:
        print(f"  Removed {removed} duplicate stories")

    return unique_stories


def sort_by_date(stories: List[Story]) -> List[Story]:
    """Sort stories by publication date, newest first."""
    return sorted(stories, key=lambda s: s.published, reverse=True)


def take_top(stories: List[Story], n: int = 25) -> List[Story]:
    """Return the top N stories (assumes already sorted by date)."""
    return stories[:n]
