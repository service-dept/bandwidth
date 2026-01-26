"""Statistics collection for bandwidth.click."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx


async def fetch_cloudflare_pageviews(
    zone_id: str, api_token: str, since_date: str | None
) -> int:
    """Fetch total pageviews from Cloudflare GraphQL Analytics API."""
    if not zone_id or not api_token:
        print(f"  Cloudflare stats skipped: zone_id={bool(zone_id)}, token={bool(api_token)}")
        return 0

    # Query up to yesterday (today's data is incomplete)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    # If no previous fetch, start from 30 days ago (max retention)
    if not since_date:
        since_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    # Skip if we've already fetched up to yesterday
    if since_date >= yesterday:
        print(f"  Cloudflare stats: already fetched up to {since_date}, skipping")
        return 0

    query = """
    query {
      viewer {
        zones(filter: { zoneTag: "%s" }) {
          httpRequests1dGroups(
            filter: { date_geq: "%s", date_leq: "%s" }
            limit: 100
          ) {
            sum { requests pageViews }
          }
        }
      }
    }
    """ % (zone_id, since_date, yesterday)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.cloudflare.com/client/v4/graphql",
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                },
                json={"query": query},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            # Debug: print raw response structure
            print(f"  Cloudflare API response keys: {data.keys()}")

            # Check for errors in response
            if "errors" in data and data["errors"]:
                print(f"  Cloudflare API errors: {data['errors']}")
                return 0

            zones = data.get("data", {}).get("viewer", {}).get("zones", [])
            if not zones:
                print(f"  Cloudflare returned no zones (check zone_id)")
                print(f"  Full response: {data}")
                return 0

            # Debug: print zone data structure
            groups = zones[0].get("httpRequests1dGroups", [])
            print(f"  Cloudflare returned {len(groups)} day(s) of data")
            if groups:
                print(f"  Sample group data: {groups[0]}")

            total = 0
            for group in groups:
                # Use pageViews if available, fall back to requests
                sum_data = group.get("sum", {})
                page_views = sum_data.get("pageViews", 0)
                requests = sum_data.get("requests", 0)
                if page_views:
                    total += page_views
                else:
                    total += requests
            print(f"  Cloudflare pageviews from {since_date} to {yesterday}: {total}")
            return total
        except Exception as e:
            print(f"Failed to fetch Cloudflare stats: {e}")
            return 0


async def fetch_github_regenerations(repo: str, token: str) -> int:
    """Fetch total workflow run count from GitHub Actions API."""
    if not repo or not token:
        print(f"  GitHub stats skipped: repo={bool(repo)}, token={bool(token)}")
        return 0

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{repo}/actions/workflows/deploy.yml/runs",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"per_page": 1},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("total_count", 0)
        except Exception as e:
            print(f"Failed to fetch GitHub stats: {e}")
            return 0


async def fetch_last_failure_date(repo: str, token: str) -> str | None:
    """Fetch the date of the most recent failed workflow run.

    Returns:
        ISO date string of last failure, or None if no failures found.
    """
    if not repo or not token:
        return None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{repo}/actions/workflows/deploy.yml/runs",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"per_page": 100, "status": "failure"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            runs = data.get("workflow_runs", [])
            if not runs:
                return None

            # Most recent failure is first
            last_failure = runs[0].get("created_at")
            return last_failure
        except Exception as e:
            print(f"Failed to fetch GitHub failure stats: {e}")
            return None


def calculate_package_size(output_path: str) -> int:
    """Calculate total size of output directory in KB."""
    output = Path(output_path)
    if not output.exists():
        return 0

    total_bytes = sum(f.stat().st_size for f in output.rglob("*") if f.is_file())
    return total_bytes // 1024


async def collect_stats(
    output_path: str,
    stats_path: str,
    seed_path: str | None = None,
) -> dict:
    """Collect and update cumulative statistics.

    Args:
        output_path: Path to the generated output directory
        stats_path: Path to stats.json file
        seed_path: Path to seed stats file (optional)

    Returns:
        Updated stats dictionary
    """
    # TODO: Add defensive parsing; corrupted stats.json currently crashes the run
    # Load existing stats, falling back to seed file if stats.json doesn't exist
    stats_file = Path(stats_path)
    seed_file = Path(seed_path) if seed_path else None

    if stats_file.exists():
        stats = json.loads(stats_file.read_text())
    elif seed_file and seed_file.exists():
        stats = json.loads(seed_file.read_text())
    else:
        stats = {
            "pageviews": 0,
            "regenerations": 0,
            "package_size_kb": 0,
            "days_since_incident": None,
            "last_updated": None,
            "last_pageview_fetch": None,
        }

    # Get environment variables for API access
    cf_zone_id = os.environ.get("CLOUDFLARE_ZONE_ID", "")
    cf_api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "")

    # Fetch new pageviews and add to cumulative total
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    new_pageviews = await fetch_cloudflare_pageviews(
        cf_zone_id, cf_api_token, stats.get("last_pageview_fetch")
    )
    if new_pageviews > 0:
        stats["pageviews"] = stats.get("pageviews", 0) + new_pageviews
        stats["last_pageview_fetch"] = yesterday  # Mark last complete day fetched

    # Fetch regeneration count (this is already cumulative from GitHub)
    regenerations = await fetch_github_regenerations(gh_repo, gh_token)
    print(f"  GitHub regenerations API returned: {regenerations}")
    if regenerations > 0:
        stats["regenerations"] = regenerations

    # Calculate current package size
    stats["package_size_kb"] = calculate_package_size(output_path)

    # Fetch days since last incident
    last_failure = await fetch_last_failure_date(gh_repo, gh_token)
    if last_failure:
        failure_date = datetime.fromisoformat(last_failure.replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - failure_date).days
        stats["days_since_incident"] = days
        print(f"  Days since last incident: {days}")
    else:
        stats["days_since_incident"] = None
        print("  No incidents recorded")

    # Update timestamps
    now = datetime.now(timezone.utc)
    stats["last_updated"] = now.isoformat()

    # Save updated stats
    stats_file.write_text(json.dumps(stats, indent=2) + "\n")

    return stats
