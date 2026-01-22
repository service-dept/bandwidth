# bandwidth.click

Bandwidth is a text-based aggregator for non-profit and open-source news. No client-side JavaScript, images, cookies, or tracking pixels to be found. WYSIWYG.

## Architecture

```
RSS Feeds → Python Pipeline → Static HTML → Cloudflare Pages CDN
```

The site regenerates every 10 minutes via GitHub Actions cron. Each build fetches fresh content from all sources, extracts full article text, and deploys ~25 stories as static HTML.

## Directory Structure

```
bandwidth/
├── src/                        # Python pipeline
│   ├── aggregator.py           # Entry point, orchestrates pipeline
│   ├── fetcher.py              # Async RSS feed fetching
│   ├── parser.py               # Feed parsing, Story dataclass
│   ├── deduplicator.py         # Deduplication and sorting
│   ├── scraper.py              # Article content extraction
│   └── generator.py            # Jinja2 HTML generation
├── templates/                  # Jinja2 templates
│   ├── base.html               # Shared layout (header, footer)
│   ├── index.html              # Homepage with story list
│   ├── story.html              # Individual story page
│   └── about.html              # About page
├── static/
│   ├── style.css               # Stylesheet
│   └── logos/                  # ASCII art logos (cycled each build)
├── config/
│   └── sources.yaml            # RSS feed configuration
├── output/                     # Generated site (gitignored)
├── .github/workflows/
│   └── deploy.yml              # CI/CD workflow
├── dev.py                      # Local dev server with hot reload
├── export_sample_data.py       # Export live data for local dev
└── sample_data.json            # Cached data for dev server
```

## Pipeline

The aggregator runs this sequence:

1. **Fetch** (`fetcher.py`) — Parallel async HTTP requests to all RSS feeds. 5-second timeout per feed. Failed feeds are skipped gracefully.

2. **Parse** (`parser.py`) — Normalize feed entries into `Story` objects. Strips HTML from titles/summaries, truncates to 280 chars, generates URL-based ID hash.

3. **Deduplicate** (`deduplicator.py`) — Remove duplicate stories by URL hash. Sort by publication date, newest first.

4. **Scrape** (`scraper.py`) — Fetch full article HTML from source URLs. Extract main content using trafilatura. 10-second timeout, 8-thread pool for CPU-bound extraction. Filters out stories where extraction fails.

5. **Generate** (`generator.py`) — Render Jinja2 templates. Writes index.html, 25 story pages, about.html, and copies static assets to `output/`.

## Python Modules

### aggregator.py

Entry point. Runs the full pipeline:

```python
async def main():
    feeds = await fetch_all_feeds("config/sources.yaml")
    stories = parse_all_feeds(feeds)
    stories = deduplicate(stories)
    stories = sort_by_date(stories)
    stories = await fetch_all_articles(stories[:30])  # fetch extra, filter failures
    stories = [s for s in stories if s.content][:25]
    generate_site(stories, "config/sources.yaml", "templates", "static", "output")
```

Run with: `python -m src.aggregator`

### fetcher.py

Async feed fetching with httpx:

- Parallel requests using `asyncio.gather`
- 5-second timeout per feed
- Returns `FeedResult(name, url, content, error)`
- Logs success/failure for each feed

### parser.py

Defines the `Story` dataclass:

```python
@dataclass
class Story:
    id: str           # 12-char SHA256 hash of source_url
    title: str        # HTML-stripped headline
    summary: str      # 280-char max description
    source: str       # Feed name (e.g., "ProPublica")
    source_url: str   # Original article URL
    published: datetime
    fetched: datetime
    content: str      # Full article HTML (added by scraper)
```

Helper functions: `strip_html()`, `truncate()`, `parse_date()`, `generate_id()`

### deduplicator.py

Simple utilities:

- `deduplicate(stories)` — Set-based dedup by story ID
- `sort_by_date(stories)` — Newest first
- `take_top(stories, n)` — Return first n stories

### scraper.py

Article content extraction:

- Fetches full HTML from article URLs (10s timeout)
- Uses trafilatura to extract main content, removing ads/nav/boilerplate
- Converts headings to `<p class="subheading">` for uniform styling
- ThreadPoolExecutor for CPU-bound trafilatura processing
- Returns None for failed extractions (story filtered out)

### generator.py

Static site generation:

- Jinja2 environment with autoescape enabled
- Custom filters: `format_date`, `format_time`, `format_datetime`, `format_iso`
- Cycles through ASCII logos in `static/logos/` (tracks index in `.logo_index`)
- Cleans output directory before each build
- Generates: index.html, story/{id}.html (x25), about.html, style.css

## Templates

Templates use Jinja2 inheritance:

**base.html** — Document structure, header with logo, footer with timestamp

**index.html** — Extends base. Loops through stories, renders headline + source + date

**story.html** — Extends base. Full article content or summary fallback. Link to original.

**about.html** — Extends base. Static content + dynamic source list from sources.yaml

### Custom Filters

```jinja2
{{ story.published | format_date }}      → "January 22, 2026"
{{ story.published | format_time }}      → "10:22 UTC"
{{ story.published | format_datetime }}  → "2026-01-22 10:22 UTC"
{{ story.published | format_iso }}       → "2026-01-22T10:22:00+00:00"
```

## Source Configuration

Edit `config/sources.yaml`:

```yaml
sources:
  - name: ProPublica
    url: https://feeds.propublica.org/propublica/main
    homepage: https://www.propublica.org
    type: rss

  - name: The Markup
    url: https://themarkup.org/feeds/rss.xml
    homepage: https://themarkup.org
    type: rss
```

Fields:
- `name` — Display name in UI
- `url` — RSS/Atom feed URL
- `homepage` — Source website (shown on about page)
- `type` — "rss" or "atom"

## Local Development

### Setup

```bash
git clone <repo>
cd bandwidth
pip install -r requirements.txt
pip install livereload watchdog  # dev dependencies
```

### Dev Server

```bash
python dev.py
```

Opens http://localhost:8000 with hot reload. Uses `sample_data.json` instead of fetching live feeds. Watches templates, static files, and sample data for changes.

### Refresh Sample Data

```bash
python export_sample_data.py
```

Fetches live feeds and exports to `sample_data.json`. Run this periodically to get fresh content for local development.

### Run Full Pipeline Locally

```bash
python -m src.aggregator
```

Fetches live feeds, scrapes articles, generates site to `output/`. Open `output/index.html` in a browser to preview.

## Production Deployment

### GitHub Actions

The workflow (`.github/workflows/deploy.yml`) runs:

- **Every 10 minutes** via cron (`*/10 * * * *`)
- **On push** to main branch
- **Manually** via workflow_dispatch

Pipeline steps:
1. Checkout code
2. Setup Python 3.11
3. Install dependencies
4. Run `python -m src.aggregator`
5. Deploy `output/` to Cloudflare Pages

### Required Secrets

Configure in GitHub repo settings → Secrets:

- `CLOUDFLARE_API_TOKEN` — API token with Pages edit permissions
- `CLOUDFLARE_ACCOUNT_ID` — Your Cloudflare account ID

### Cloudflare Pages

The site is served from Cloudflare Pages CDN. Configuration in `wrangler.toml`:

```toml
name = "bandwidth"
pages_build_output_dir = "output"
```

## Configuration Files

### pyproject.toml

Project metadata and dependencies:

```toml
[project]
name = "bandwidth"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "feedparser>=6.0",
    "jinja2>=3.1",
    "httpx>=0.27",
    "pyyaml>=6.0",
]
```

### requirements.txt

Pip dependencies for CI:

```
feedparser
httpx
pyyaml
jinja2
trafilatura
lxml_html_clean
```

### wrangler.toml

Cloudflare Pages configuration. The `pages_build_output_dir` points to the generated `output/` directory.
