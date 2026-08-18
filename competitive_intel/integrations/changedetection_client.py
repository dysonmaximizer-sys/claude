"""
changedetection.io integration — polls watches for page changes detected
since the last lookback window.

API base: configured via CHANGEDETECTION_BASE_URL (e.g. https://<account>.changedetection.io)
Auth:     x-api-key: <api_key> header
Docs:     https://changedetection.io/docs/api_v1/index.html

How change detection works:
  - GET /api/v1/watch                            → list every watch (page being monitored)
  - GET /api/v1/watch/{uuid}                     → watch detail with last_changed timestamp
  - GET /api/v1/watch/{uuid}/history             → dict of timestamps for prior snapshots
  - GET /api/v1/watch/{uuid}/history/{timestamp} → the plain-text snapshot at that point in time

For each watch whose last_changed falls inside the lookback window, we pull the
two most recent snapshots, diff them locally with difflib, and pass the diff
through to daily_poll.py for scoring.

Watches are mapped to competitors by _match_competitor() using the url_patterns
and title_patterns in config.COMPETITORS. A watch that matches nothing is
skipped with a WARNING naming the URL — that log line is the signal that a
competitor is being monitored in changedetection.io but is missing from the
registry.
"""

import logging
import os
import difflib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# Load .env relative to this file so vars are available regardless of CWD
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from config import COMPETITORS

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("CHANGEDETECTION_API_KEY", "")
_BASE_URL = os.environ.get("CHANGEDETECTION_BASE_URL", "").rstrip("/")
_HEADERS = {"x-api-key": _API_KEY}


# ── API wrappers ──────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get_json(path: str) -> dict:
    r = requests.get(f"{_BASE_URL}{path}", headers=_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get_text(path: str) -> str:
    r = requests.get(f"{_BASE_URL}{path}", headers=_HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


# ── Public API ────────────────────────────────────────────────────────────────

def get_recent_changes(lookback_hours: int = 25) -> list[dict]:
    """
    Poll changedetection.io for watches that changed within the lookback window.

    Returns a list of change dicts shaped for the daily_poll pipeline:
      {competitor_name, tier, url, raw_change, category, source_type, detected_at}
    """
    # Raise rather than return [] on a broken fetch. Returning an empty list
    # made a cd.io outage or a missing key indistinguishable from "no changes
    # today": the job logged an ERROR and then exited 0, so the scheduled run
    # went green while nothing was being monitored. daily_poll already wraps
    # this call and counts a raise as an error.
    if not _API_KEY or not _BASE_URL:
        raise RuntimeError(
            "changedetection.io is not configured — set CHANGEDETECTION_API_KEY "
            "and CHANGEDETECTION_BASE_URL in .env"
        )

    cutoff = datetime.now(timezone.utc).timestamp() - (lookback_hours * 3600)

    watches = _get_json("/api/v1/watch")

    out: list[dict] = []
    for uuid, meta in watches.items():
        last_changed = meta.get("last_changed", 0) or 0
        if last_changed < cutoff:
            continue

        url = meta.get("link") or meta.get("url", "")
        title = meta.get("title") or meta.get("page_title") or ""

        competitor = _match_competitor(title, url)
        if not competitor:
            logger.warning(
                "Skipping changed watch (no competitor match) — url=%s title=%r. "
                "Add a url_patterns entry to COMPETITORS in config.py to capture it.",
                url, title,
            )
            continue

        diff_text = _fetch_latest_diff(uuid)
        if not diff_text:
            logger.info("No diffable history yet for %s (%s) — skipping", competitor, url)
            continue

        out.append({
            "competitor_name": competitor,
            "tier": COMPETITORS[competitor]["tier"],
            "url": url,
            "raw_change": diff_text[:5000],
            "category": "Other",  # Claude classifies during scoring
            "source_type": "Web",
            "detected_at": datetime.fromtimestamp(last_changed, tz=timezone.utc).isoformat(),
        })

    logger.info("changedetection.io returned %d competitor-matched changes", len(out))
    return out


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_url(url: str) -> tuple:
    """Return (host, path) lowercased, with any leading 'www.' left intact."""
    try:
        parsed = urlparse(url if "//" in url else f"https://{url}")
    except ValueError:
        return "", ""
    return (parsed.hostname or "").lower(), (parsed.path or "").lower()


def _host_matches(host: str, pattern_host: str) -> bool:
    """
    True if `host` is `pattern_host` or a subdomain of it.

    Suffix matching on the dot boundary, not a plain substring: "act.com"
    must not match "contact.com" or "exact.com".
    """
    if not host or not pattern_host:
        return False
    return host == pattern_host or host.endswith(f".{pattern_host}")


def _match_competitor(title: str, url: str) -> Optional[str]:
    """
    Resolve a watch to a competitor, in order of precision:

      1. url_patterns   — (host_suffix, optional path substring) from the
         registry. Most specific match wins, so a broad host pattern can't
         outrank a host+path one.
      2. title_patterns — regexes against the watch title, for watches whose
         URL doesn't carry the brand (e.g. a LinkedIn showcase page).
      3. slug fallback  — legacy "slug appears anywhere in title+url" check,
         kept for the original 11 competitors so their existing watches keep
         matching untouched. Competitors whose slug is a common substring set
         slug_match=False and rely on the two precise passes above.

    Returns the competitor name, or None if nothing matches.
    """
    host, path = _split_url(url)

    best_name, best_specificity = None, -1
    for name, meta in COMPETITORS.items():
        for pattern_host, pattern_path in meta.get("url_patterns", []):
            if not _host_matches(host, pattern_host):
                continue
            if pattern_path and pattern_path not in path:
                continue
            specificity = len(pattern_host) + len(pattern_path or "")
            if specificity > best_specificity:
                best_name, best_specificity = name, specificity
    if best_name:
        return best_name

    title_lower = (title or "").lower()
    for name, meta in COMPETITORS.items():
        for pattern in meta.get("title_patterns", []):
            if re.search(pattern, title_lower):
                return name

    haystack = f"{title} {url}".lower()
    for name, meta in COMPETITORS.items():
        if meta.get("slug_match", True) and meta["slug"].lower() in haystack:
            return name
    return None


def _fetch_latest_diff(uuid: str) -> str:
    """
    Pull the two most recent text snapshots for this watch and return a compact
    unified diff. Returns an empty string if fewer than 2 snapshots exist or any
    fetch fails.
    """
    try:
        history = _get_json(f"/api/v1/watch/{uuid}/history")
    except Exception as e:
        logger.error("Failed to read history for %s: %s", uuid, e)
        return ""

    timestamps = sorted(history.keys())
    if len(timestamps) < 2:
        return ""

    latest_ts, prev_ts = timestamps[-1], timestamps[-2]

    try:
        latest_text = _get_text(f"/api/v1/watch/{uuid}/history/{latest_ts}")
        prev_text = _get_text(f"/api/v1/watch/{uuid}/history/{prev_ts}")
    except Exception as e:
        logger.error("Failed to fetch snapshots for %s: %s", uuid, e)
        return ""

    return _build_diff(prev_text, latest_text)


def _build_diff(old: str, new: str) -> str:
    """Generate a compact unified diff between two text snapshots."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff_lines = difflib.unified_diff(old_lines, new_lines, lineterm="", n=2)
    # Drop the unified-diff file header lines (--- / +++) — they're noise here
    body = [
        line for line in diff_lines
        if not (line.startswith("---") or line.startswith("+++"))
    ]
    return "\n".join(body)
