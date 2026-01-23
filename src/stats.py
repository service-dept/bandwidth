"""Statistics collection for bandwidth.click."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx


async def fetch_cloudflare_visitors(
    zone_id: str, api_token: str, since_date: str | None
) -> int:
    """Fetch unique visitors from Cloudflare GraphQL Analytics API."""
    if not zone_id or not api_token:
        return 0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # If no previous fetch, start from 30 days ago (max retention)
    if not since_date:
        since_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    query = """
    query {
      viewer {
        zones(filter: { zoneTag: "%s" }) {
          httpRequests1dGroups(
            filter: { date_geq: "%s", date_lt: "%s" }
            limit: 100
          ) {
            uniq { uniques }
          }
        }
      }
    }
    """ % (zone_id, since_date, today)

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

            # Sum up unique visitors from all days
            zones = data.get("data", {}).get("viewer", {}).get("zones", [])
            if not zones:
                return 0

            total = 0
            for group in zones[0].get("httpRequests1dGroups", []):
                total += group.get("uniq", {}).get("uniques", 0)
            return total
        except Exception as e:
            print(f"Failed to fetch Cloudflare stats: {e}")
            return 0


async def fetch_github_regenerations(repo: str, token: str) -> int:
    """Fetch total workflow run count from GitHub Actions API."""
    if not repo or not token:
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
    stories_count: int = 25,
) -> dict:
    """Collect and update cumulative statistics.

    Args:
        output_path: Path to the generated output directory
        stats_path: Path to stats.json file
        stories_count: Number of stories rendered this build

    Returns:
        Updated stats dictionary
    """
    # Load existing stats
    stats_file = Path(stats_path)
    if stats_file.exists():
        stats = json.loads(stats_file.read_text())
    else:
        stats = {
            "visitors": 0,
            "regenerations": 0,
            "stories_rendered": 0,
            "package_size_kb": 0,
            "last_updated": None,
            "last_visitor_fetch": None,
        }

    # Get environment variables for API access
    cf_zone_id = os.environ.get("CLOUDFLARE_ZONE_ID", "")
    cf_api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "")

    # Fetch new visitors and add to cumulative total
    new_visitors = await fetch_cloudflare_visitors(
        cf_zone_id, cf_api_token, stats.get("last_visitor_fetch")
    )
    stats["visitors"] += new_visitors

    # Fetch regeneration count (this is already cumulative from GitHub)
    regenerations = await fetch_github_regenerations(gh_repo, gh_token)
    if regenerations > 0:
        stats["regenerations"] = regenerations

    # Increment stories rendered
    stats["stories_rendered"] += stories_count

    # Calculate current package size
    stats["package_size_kb"] = calculate_package_size(output_path)

    # Update timestamps
    now = datetime.now(timezone.utc)
    stats["last_updated"] = now.isoformat()
    stats["last_visitor_fetch"] = now.strftime("%Y-%m-%d")

    # Save updated stats
    stats_file.write_text(json.dumps(stats, indent=2) + "\n")

    return stats
