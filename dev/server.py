#!/usr/bin/env python3
"""
Local development server with hot reload.

Usage:
    pip install -e ".[dev]"
    python dev/server.py

Opens http://localhost:8000 with live reload on template/CSS changes.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from livereload import Server

# Paths
DEV_DIR = Path(__file__).parent
ROOT = DEV_DIR.parent
TEMPLATES_PATH = ROOT / "templates"
STATIC_PATH = ROOT / "static"
OUTPUT_PATH = ROOT / "output"
SAMPLE_DATA_PATH = DEV_DIR / "sample_data.json"
SOURCES_PATH = ROOT / "config" / "sources.yaml"
SAMPLE_STATS_PATH = DEV_DIR / "sample_stats.json"


@dataclass
class Story:
    """A single news story (mirrors src.parser.Story)."""

    id: str
    title: str
    summary: str
    source: str
    source_url: str
    published: datetime
    fetched: datetime
    content: str = ""


def load_sample_data() -> tuple[list[Story], list[dict], dict]:
    """Load sample stories from JSON, sources from YAML, and stats."""
    with open(SAMPLE_DATA_PATH) as f:
        data = json.load(f)

    stories = []
    for s in data["stories"]:
        stories.append(
            Story(
                id=s["id"],
                title=s["title"],
                summary=s["summary"],
                source=s["source"],
                source_url=s["source_url"],
                published=datetime.fromisoformat(s["published"].replace("Z", "+00:00")),
                fetched=datetime.fromisoformat(s["fetched"].replace("Z", "+00:00")),
                content=s.get("content", ""),
            )
        )

    # Load sources directly from YAML (authoritative source)
    with open(SOURCES_PATH) as f:
        sources_config = yaml.safe_load(f)
    sources = sources_config.get("sources", [])

    # Load sample stats for dev server
    stats = None
    if SAMPLE_STATS_PATH.exists():
        with open(SAMPLE_STATS_PATH) as f:
            stats = json.load(f)

    return stories, sources, stats


def create_environment() -> Environment:
    """Create Jinja2 environment with filters."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_PATH)),
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


def load_next_logo() -> str:
    """Load the next logo in sequence from the logos directory."""
    logos_dir = STATIC_PATH / "logos"
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


def generate_site() -> None:
    """Generate the complete static site from sample data."""
    OUTPUT_PATH.mkdir(exist_ok=True)

    # Clean output directory
    for item in OUTPUT_PATH.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    stories, sources, stats = load_sample_data()
    env = create_environment()
    now = datetime.now(timezone.utc)
    logo = load_next_logo()

    # Generate index.html
    template = env.get_template("index.html")
    html = template.render(stories=stories, updated=now, logo=logo, stats=stats)
    (OUTPUT_PATH / "index.html").write_text(html)
    print("  Generated index.html")

    # Generate story pages
    story_dir = OUTPUT_PATH / "story"
    story_dir.mkdir(exist_ok=True)
    template = env.get_template("story.html")
    for story in stories:
        html = template.render(story=story, updated=now, logo=logo, stats=stats)
        (story_dir / f"{story.id}.html").write_text(html)
    print(f"  Generated {len(stories)} story pages")

    # Generate static pages (only if template exists)
    for page in ["about", "sources", "support"]:
        template_file = TEMPLATES_PATH / f"{page}.html"
        if template_file.exists():
            template = env.get_template(f"{page}.html")
            html = template.render(sources=sources, updated=now, logo=logo, stats=stats)
            (OUTPUT_PATH / f"{page}.html").write_text(html)
            print(f"  Generated {page}.html")

    # Copy static files
    if STATIC_PATH.exists():
        for item in STATIC_PATH.iterdir():
            if item.is_file():
                shutil.copy(item, OUTPUT_PATH / item.name)
        print("  Copied static files")


def kill_existing_dev_server(port: int = 8000) -> bool:
    """Kill any existing dev.py process using the specified port."""
    try:
        # Find process using the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return False

        pids = result.stdout.strip().split("\n")
        for pid in pids:
            # Check if it's a python dev.py process
            try:
                cmd_result = subprocess.run(
                    ["ps", "-p", pid, "-o", "command="],
                    capture_output=True,
                    text=True,
                )
                if "dev/server.py" in cmd_result.stdout or "dev.py" in cmd_result.stdout:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"  Killed existing dev server (PID {pid})")
                    return True
            except (ProcessLookupError, ValueError):
                continue
        return False
    except FileNotFoundError:
        # lsof not available
        return False


def main():
    """Start the development server."""
    print("Bandwidth Dev Server")
    print("=" * 40)

    # Kill any existing dev server on port 8000
    kill_existing_dev_server(8000)

    # Initial build
    print("\nBuilding site...")
    generate_site()

    port = 8000

    # Create livereload server
    server = Server()

    # Watch templates and static files for changes
    server.watch(str(TEMPLATES_PATH / "*.html"), generate_site)
    server.watch(str(STATIC_PATH / "*"), generate_site)
    server.watch(str(SAMPLE_DATA_PATH), generate_site)
    server.watch(str(SOURCES_PATH), generate_site)

    # Wrap the WSGI app to regenerate on each HTML request (rotates logos)
    from livereload.server import StaticFileHandler
    original_get = StaticFileHandler.get

    def regenerating_get(self, path='', *args, **kwargs):
        if path.endswith('.html') or path == '' or '.' not in path.split('/')[-1]:
            generate_site()
        return original_get(self, path, *args, **kwargs)

    StaticFileHandler.get = regenerating_get

    print(f"\nServing {OUTPUT_PATH}/ at http://localhost:{port}")
    print("Watching for changes in templates/, static/, and config/")
    print("Press Ctrl+C to stop\n")

    # Serve output directory with live reload
    server.serve(root=str(OUTPUT_PATH), port=port, open_url_delay=1)


if __name__ == "__main__":
    main()
