"""Generate static HTML from stories."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import yaml
from jinja2 import Environment, FileSystemLoader

from .parser import Story


def create_environment(templates_path: str) -> Environment:
    """Create Jinja2 environment."""
    env = Environment(
        loader=FileSystemLoader(templates_path),
        autoescape=True,
    )

    def format_date(dt: datetime) -> str:
        return dt.strftime("%B %d, %Y")

    def format_time(dt: datetime) -> str:
        return dt.strftime("%H:%M UTC")

    def format_datetime(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M UTC")

    def format_iso(dt: datetime) -> str:
        return dt.isoformat()

    env.filters["format_date"] = format_date
    env.filters["format_time"] = format_time
    env.filters["format_datetime"] = format_datetime
    env.filters["format_iso"] = format_iso

    return env


def generate_site(
    stories: List[Story],
    templates_path: str,
    static_path: str,
    output_path: str,
    sources_path: str,
) -> None:
    """Generate the complete static site."""
    output = Path(output_path)
    output.mkdir(exist_ok=True)

    # Clean output directory
    for item in output.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    env = create_environment(templates_path)
    now = datetime.now(timezone.utc)

    # Load sources for sources page
    with open(sources_path) as f:
        sources_config = yaml.safe_load(f)
    sources = sources_config.get("sources", [])

    # Generate index.html
    template = env.get_template("index.html")
    html = template.render(stories=stories, updated=now)
    (output / "index.html").write_text(html)
    print("  Generated index.html")

    # Generate story pages
    story_dir = output / "story"
    story_dir.mkdir(exist_ok=True)
    template = env.get_template("story.html")
    for story in stories:
        html = template.render(story=story, updated=now)
        (story_dir / f"{story.id}.html").write_text(html)
    print(f"  Generated {len(stories)} story pages")

    # Generate static pages
    for page in ["about", "sources", "support"]:
        template = env.get_template(f"{page}.html")
        html = template.render(sources=sources, updated=now)
        (output / f"{page}.html").write_text(html)
        print(f"  Generated {page}.html")

    # Copy static files
    static = Path(static_path)
    if static.exists():
        for item in static.iterdir():
            if item.is_file():
                shutil.copy(item, output / item.name)
        print("  Copied static files")

    print(f"\nSite generated in {output_path}/")
