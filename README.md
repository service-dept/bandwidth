# bandwidth

**A text-based, bandwidth-friendly news aggregator.**

Website: [https://bandwidth.click](https://bandwidth.click)

---

## What is bandwidth?

bandwidth is a news aggregator that strips away everything unnecessary. No JavaScript. No images. No cookies. No tracking. Just news, in plain text, that loads instantly on any connection.

The site pulls content from public RSS feeds, APIs, and open source news projects, then regenerates every 10 minutes to keep things fresh.

---

## Brand Definition

### Mission

To deliver news without the bloat. bandwidth exists for people who want information, not distractions—readers on slow connections, those who value privacy, or anyone tired of the modern web's excess.

### Core Values

- **Simplicity** — Text is enough. If it doesn't need to be there, it isn't.
- **Privacy** — No cookies, no tracking, no data collection. Ever.
- **Accessibility** — Works on any device, any connection, any browser.
- **Independence** — 100% audience-funded. No corporate advertising.

### Voice & Tone

bandwidth speaks plainly. No marketing fluff, no clickbait, no sensationalism. The brand is:

- Direct and honest
- Technical but approachable
- Quietly confident
- Anti-hype

### Visual Identity

- System default fonts
- Minimal CSS—polished but clearly default HTML elements
- No logos, icons, or decorative elements
- Minimal use of color (links only)

---

## Alpha Tech Design

### Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.11+ |
| RSS parsing | `feedparser` |
| Templating | `jinja2` |
| HTTP requests | `httpx` (async) |
| Hosting | Cloudflare Pages |
| Scheduler | Cloudflare Workers (cron trigger every 10 min) |
| Domain | bandwidth.click |

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Cloudflare Workers                       │
│                    (cron trigger: */10 * * * *)                 │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Python Aggregator                          │
│  1. Fetch RSS feeds + open source APIs                          │
│  2. Parse & normalize stories                                   │
│  3. Deduplicate by URL/title similarity                         │
│  4. Sort by timestamp (newest first)                            │
│  5. Take top 25                                                 │
│  6. Generate HTML via Jinja2                                    │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Cloudflare Pages                           │
│                 Static HTML served globally                     │
└─────────────────────────────────────────────────────────────────┘
```

### Content Sources (Alpha)

**Major RSS Feeds (5):**
1. Associated Press — `https://apnews.com/index.rss`
2. Reuters — `https://www.reutersagency.com/feed/`
3. NPR News — `https://feeds.npr.org/1001/rss.xml`
4. BBC World — `https://feeds.bbci.co.uk/news/world/rss.xml`
5. Al Jazeera — `https://www.aljazeera.com/xml/rss/all.xml`

**Open Source News Projects (5):**
1. Wikinews — `https://en.wikinews.org/w/index.php?title=Special:NewsFeed&feed=rss`
2. The Conversation — `https://theconversation.com/articles.rss`
3. ProPublica — `https://www.propublica.org/feeds/propublica/main`
4. The Markup — `https://themarkup.org/feeds/rss.xml`
5. Ground News (API) — open aggregation data

### Repository Structure

```
bandwidth/
├── README.md
├── pyproject.toml              # Python dependencies
├── src/
│   ├── __init__.py
│   ├── aggregator.py           # Main entry point
│   ├── fetcher.py              # Async RSS/API fetching
│   ├── parser.py               # Normalize stories from different sources
│   ├── deduplicator.py         # Remove duplicate stories
│   └── generator.py            # Jinja2 HTML generation
├── templates/
│   ├── base.html               # Shared layout
│   ├── index.html              # Homepage (feed)
│   ├── story.html              # Individual story detail page
│   ├── about.html              # About page
│   ├── sources.html            # Source list
│   └── support.html            # Funding page
├── static/
│   └── style.css               # Minimal CSS
├── output/                     # Generated HTML (gitignored)
├── config/
│   └── sources.yaml            # RSS feed URLs and config
├── worker/
│   └── index.js                # Cloudflare Worker cron trigger
└── wrangler.toml               # Cloudflare config
```

### Data Model

```python
@dataclass
class Story:
    id: str              # SHA256 hash of URL
    title: str           # Headline
    summary: str         # Short description (max 280 chars)
    source: str          # "Associated Press", "BBC", etc.
    source_url: str      # Link to original article
    published: datetime  # Publication timestamp
    fetched: datetime    # When we fetched it
```

### Page Specifications

**Homepage (`index.html`):**
- 25 most recent stories
- Each story shows: headline, source, timestamp, summary
- Headline links to detail page (`/story/{id}.html`)
- Footer: "Last updated: {timestamp}" + links to About, Sources, Support

**Story Detail Page (`/story/{id}.html`):**
- Full headline
- Source + publication date
- Summary
- "Read full article →" link to original source
- "← Back to feed" link

**About Page (`about.html`):**
- What bandwidth is
- Privacy commitment (no JS, cookies, tracking)
- Funding model
- Contact info

**Sources Page (`sources.html`):**
- List of all RSS feeds and APIs used
- Links to each source's homepage

**Support Page (`support.html`):**
- How to fund bandwidth
- Donation links (added later)

### HTML/CSS Guidelines

- Semantic HTML5 (`<article>`, `<header>`, `<main>`, `<footer>`, `<time>`)
- Single `style.css` file, <1KB
- No classes except for minimal layout
- System font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- Browser default styling with light polish:
  - Reasonable max-width for readability (~70ch)
  - Comfortable line-height (1.5)
  - Subtle link styling
- Must be fully readable with CSS disabled
- No media queries for alpha (works naturally on all screen sizes)

### Build Steps (Alpha)

1. **Setup**
   - Create GitHub repo
   - Initialize Python project with `pyproject.toml`
   - Install dependencies: `feedparser`, `jinja2`, `httpx`, `pyyaml`

2. **Fetcher module**
   - Async fetch all RSS feeds in parallel
   - Handle timeouts gracefully (5s per feed)
   - Return raw feed data

3. **Parser module**
   - Normalize RSS items to `Story` dataclass
   - Strip HTML from summaries
   - Truncate summaries to 280 chars
   - Parse dates to UTC datetime

4. **Deduplicator module**
   - Hash URLs to detect exact duplicates
   - Optional: fuzzy title matching for near-duplicates

5. **Generator module**
   - Load Jinja2 templates
   - Render `index.html` with top 25 stories
   - Render individual `story/{id}.html` pages
   - Render static pages (about, sources, support)
   - Write all to `output/` directory

6. **Templates**
   - Create `base.html` with shared structure
   - Create page templates extending base
   - Create `style.css` with minimal styling

7. **Local testing**
   - Run aggregator locally
   - Serve `output/` with `python -m http.server`
   - Verify all pages render correctly

8. **Cloudflare setup**
   - Connect GitHub repo to Cloudflare Pages
   - Configure build command: `python src/aggregator.py`
   - Configure output directory: `output`
   - Add bandwidth.click domain

9. **Cloudflare Worker (cron)**
   - Create Worker that triggers Pages rebuild
   - Set cron schedule: `*/10 * * * *`
   - Deploy with Wrangler

### Dependencies

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

[project.optional-dependencies]
dev = [
    "ruff",
    "pytest",
]
```

---

## Future Enhancements (Post-Alpha)

- Daily archives
- Topic categories/filtering
- Search
- Email digest (opt-in, no tracking)
- Dark mode toggle (CSS only, via query param)
- More sources

---

## Funding Model

bandwidth is 100% audience-funded. No corporate advertising. No sponsored content. No data sales.

Options:
- Ko-fi or Buy Me a Coffee (simple, no platform fees)
- GitHub Sponsors
- Direct donations via Stripe

---

## License

MIT

---

*bandwidth — news without the noise.*
