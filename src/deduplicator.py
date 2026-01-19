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


def take_top(stories: List[Story], n: int = 25, min_per_source: int = 1) -> List[Story]:
    """Return the top N stories, ensuring minimum representation per source.

    First includes the most recent story from each source, then fills
    remaining slots with the most recent stories overall.
    """
    if not stories:
        return []

    # Get unique sources
    sources = set(s.source for s in stories)

    # Get the most recent story from each source
    selected: List[Story] = []
    selected_ids: Set[str] = set()

    for source in sources:
        source_stories = [s for s in stories if s.source == source]
        for story in source_stories[:min_per_source]:
            if story.id not in selected_ids:
                selected.append(story)
                selected_ids.add(story.id)

    # Fill remaining slots with most recent stories not yet selected
    remaining_slots = n - len(selected)
    if remaining_slots > 0:
        for story in stories:
            if story.id not in selected_ids:
                selected.append(story)
                selected_ids.add(story.id)
                if len(selected) >= n:
                    break

    # Sort final selection by date
    selected.sort(key=lambda s: s.published, reverse=True)

    return selected
