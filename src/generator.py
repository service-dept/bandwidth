"""Generate static HTML from stories."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from .parser import Story


def load_next_logo(static_path: str) -> str:
    """Load the next logo in sequence from the logos directory."""
    logos_dir = Path(static_path) / "logos"
    logo_files = sorted(logos_dir.glob("logo-*.html"))
    if not logo_files:
        return "<h1><a href='/'>Bandwidth</a></h1>"

    # Track which logo to use next
    state_file = logos_dir / ".logo_index"
    try:
        index = int(state_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        index = 0

    # Wrap around if needed
    index = index % len(logo_files)
    logo_file = logo_files[index]

    # Save next index
    state_file.write_text(str((index + 1) % len(logo_files)))

    return logo_file.read_text()


def create_environment(templates_path: str) -> Environment:
    """Create Jinja2 environment."""
    env = Environment(
        loader=FileSystemLoader(templates_path),
        autoescape=True,
    )

    def format_date(dt: datetime) -> str:
        return dt.strftime("%b %d, %Y")

    def format_time(dt: datetime) -> str:
        return dt.strftime("%H:%M UTC")

    def format_datetime(dt: datetime) -> str:
        return dt.strftime("%b %d %Y %H:%M UTC")

    def format_iso(dt: datetime) -> str:
        return dt.isoformat()

    env.filters["format_date"] = format_date
    env.filters["format_time"] = format_time
    env.filters["format_datetime"] = format_datetime
    env.filters["format_iso"] = format_iso

    return env


def generate_site(
    stories: list[Story],
    templates_path: str,
    static_path: str,
    output_path: str,
    sources_path: str,
    stats: dict | None = None,
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

    # Load next logo in sequence
    logo = load_next_logo(static_path)

    # TODO: Validate required fields (name, homepage) to avoid KeyError crashes
    # Load sources for sources page
    with open(sources_path) as f:
        sources_config = yaml.safe_load(f)
    sources = sources_config.get("sources", [])

    # Generate index.html
    template = env.get_template("index.html")
    html = template.render(stories=stories, updated=now, logo=logo, stats=stats)
    (output / "index.html").write_text(html)
    print("  Generated index.html")

    # Generate story pages
    story_dir = output / "story"
    story_dir.mkdir(exist_ok=True)
    template = env.get_template("story.html")
    for story in stories:
        html = template.render(story=story, updated=now, logo=logo, stats=stats)
        (story_dir / f"{story.id}.html").write_text(html)
    print(f"  Generated {len(stories)} story pages")

    # Generate about page
    template = env.get_template("about.html")
    html = template.render(sources=sources, updated=now, logo=logo, stats=stats)
    (output / "about.html").write_text(html)
    print("  Generated about.html")

    # Copy static files
    static = Path(static_path)
    if static.exists():
        for item in static.iterdir():
            if item.is_file():
                shutil.copy(item, output / item.name)
        print("  Copied static files")

    print(f"\nSite generated in {output_path}/")
