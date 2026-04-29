"""
Visualping integration — polls job history for detected page changes.

API base: https://job.api.visualping.io
Auth:     Authorization: Bearer <api_key>
Docs:     https://api.visualping.io/

How change detection works:
  - GET /v2/jobs          → list all monitored jobs
  - GET /v2/jobs/{jobId}  → job detail including history[]
  - Each history entry has PercentDifference and diff.changeDetectionLevel
  - When PercentDifference > 0, the page changed between that run and the previous
  - We fetch both HTML snapshots and diff them to get the raw change text
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config import VISUALPING_API_KEY, COMPETITORS

logger = logging.getLogger(__name__)

BASE_URL = "https://job.api.visualping.io"
HEADERS = {"Authorization": f"Bearer {VISUALPING_API_KEY}"}


# ── API Wrappers ───────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get(path: str, params: Optional[dict] = None) -> dict:
    url = f"{BASE_URL}{path}"
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


# ── Public Interface ───────────────────────────────────────────────────────────

def get_recent_changes(lookback_hours: int = 25) -> list[dict]:
    """
    Main entry point for the daily poll job.

    Iterates all Visualping jobs, finds history entries from the last
    `lookback_hours` that show a real change, and returns normalised
    change dicts ready for Notion logging.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    jobs_data = _get("/v2/jobs", params={"pageSize": 100})
    jobs = jobs_data.get("jobs", [])
    logger.info("Found %d monitored jobs in Visualping", len(jobs))

    all_changes: list[dict] = []

    for job in jobs:
        job_id = str(job["id"])
        url = job.get("url", "")
        description = job.get("description", "")

        competitor_name = _match_competitor(description, url)
        if not competitor_name:
            logger.debug("Skipping unmatched job: %s (%s)", description[:60], url)
            continue

        changes = _get_changes_for_job(job_id, url, competitor_name, since)
        all_changes.extend(changes)

    logger.info("Collected %d new change events across all jobs", len(all_changes))
    return all_changes


# ── Per-Job Change Detection ───────────────────────────────────────────────────

def _get_changes_for_job(
    job_id: str,
    url: str,
    competitor_name: str,
    since: datetime,
) -> list[dict]:
    """
    For a single job, return any real changes detected since `since`.
    """
    try:
        detail = _get(f"/v2/jobs/{job_id}")
    except requests.HTTPError as e:
        logger.warning("Could not fetch detail for job %s: %s", job_id, e)
        return []

    history = detail.get("history", [])
    if len(history) < 2:
        return []

    results = []

    # History is newest-first (index 0 = most recent snapshot).
    # Iterate from newest toward oldest; for each entry, history[i+1] is the
    # prior snapshot to diff against.  We stop processing the very last entry
    # because there is nothing older to diff it against.
    for i in range(len(history) - 1):
        entry = history[i]
        created_str = entry.get("created", "")

        # Parse timestamp
        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        if created < since:
            break  # All subsequent entries are even older — stop

        if not _is_significant_change(entry):
            continue

        # history[i+1] is the previous (older) snapshot
        prev_entry = history[i + 1]
        raw_change = _extract_change_text(entry, prev_entry, url)

        if raw_change:
            results.append(
                _normalise_change(
                    entry=entry,
                    raw_change=raw_change,
                    competitor_name=competitor_name,
                    url=url,
                )
            )

    return results


def _is_significant_change(entry: dict) -> bool:
    """Return True if this history entry represents a real page change."""
    if entry.get("initial"):
        return False  # First-ever snapshot, not a change

    percent_diff = entry.get("PercentDifference", 0)
    if isinstance(percent_diff, (int, float)) and percent_diff > 0:
        return True

    level = entry.get("diff", {}).get("changeDetectionLevel", "none")
    return level not in ("none", "")


def _extract_change_text(current: dict, previous: dict, url: str) -> str:
    """
    Fetch both HTML snapshots and return a plain-text summary of what changed.
    Falls back to the current page text if the diff can't be computed.
    """
    current_html_url = current.get("html", "")
    prev_html_url = previous.get("html", "")

    current_text = _fetch_html_as_text(current_html_url)
    prev_text = _fetch_html_as_text(prev_html_url)

    if not current_text:
        return ""

    if prev_text and current_text != prev_text:
        diff = _text_diff(prev_text, current_text)
        return diff if diff else current_text[:3000]

    return current_text[:3000]


def _fetch_html_as_text(html_url: str) -> str:
    """Fetch a Visualping HTML snapshot and return stripped plain text."""
    if not html_url:
        return ""
    try:
        r = requests.get(html_url, timeout=20)
        r.raise_for_status()
        return _strip_html(r.text)
    except Exception as e:
        logger.debug("Could not fetch snapshot %s: %s", html_url, e)
        return ""


def _strip_html(html: str) -> str:
    """Convert HTML to plain text using Python's built-in parser."""

    class _Stripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "head"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "head"):
                self._skip = False
            if tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "li"):
                self.parts.append("\n")

        def handle_data(self, data):
            if not self._skip:
                self.parts.append(data)

    stripper = _Stripper()
    stripper.feed(html)
    text = "".join(stripper.parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:4000]


def _text_diff(old: str, new: str) -> str:
    """
    Return a compact summary of lines added/removed between two text snapshots.
    """
    old_lines = set(old.splitlines())
    new_lines = set(new.splitlines())

    added = [l for l in new.splitlines() if l.strip() and l not in old_lines]
    removed = [l for l in old.splitlines() if l.strip() and l not in new_lines]

    parts = []
    if removed:
        parts.append("REMOVED:\n" + "\n".join(f"- {l}" for l in removed[:30]))
    if added:
        parts.append("ADDED:\n" + "\n".join(f"+ {l}" for l in added[:30]))

    return "\n\n".join(parts)[:3000]


def _normalise_change(
    entry: dict,
    raw_change: str,
    competitor_name: str,
    url: str,
) -> dict:
    """Build a standard change dict from a Visualping history entry."""
    percent = entry.get("PercentDifference", 0)
    level = entry.get("diff", {}).get("changeDetectionLevel", "unknown")

    return {
        "competitor_name": competitor_name,
        "tier": COMPETITORS[competitor_name]["tier"],
        "url": url,
        "raw_change": raw_change,
        "detected_at": entry.get("created", ""),
        "category": _infer_category(url, raw_change),
        "source_type": "Web",
        "visualping_job_id": "",  # set by caller if needed
        "change_percent": percent,
        "change_level": level,
    }


# ── Competitor Matching ────────────────────────────────────────────────────────

def _match_competitor(description: str, url: str) -> Optional[str]:
    """
    Match a Visualping job to a known competitor using slug/name matching
    against both the job description and the URL.
    """
    combined = f"{description} {url}".lower()
    for comp_name, meta in COMPETITORS.items():
        if meta["slug"] in combined or comp_name.lower() in combined:
            return comp_name
    return None


def _infer_category(url: str, text: str) -> str:
    """Heuristic category from URL and change text. Refined later by scoring agent."""
    url_lower = url.lower()
    text_lower = str(text).lower()

    if any(k in url_lower for k in ["pric", "plan", "billing"]):
        return "Pricing"
    if any(k in url_lower for k in ["feature", "product", "solution"]):
        return "Feature"
    if any(k in text_lower for k in ["price", "plan", "$", "per month", "annually", "pricing"]):
        return "Pricing"
    if any(k in text_lower for k in ["new feature", "release", "launch", "introducing", "now available"]):
        return "Feature"
    if any(k in text_lower for k in ["partner", "integrat"]):
        return "Integration"
    return "Messaging"
