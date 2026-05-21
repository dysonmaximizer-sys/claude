"""
Notion integration — single source of truth for all competitor changes.

Uses raw HTTP requests throughout to avoid notion-client version incompatibilities.

Database managed here:
  - Changes: every detected change, with score, summary, and distribution status
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# Load .env relative to this file so env vars are available regardless of CWD
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

# Loaded directly from env (config.py imports us, so avoid circular import)
_TOKEN = os.environ.get("NOTION_TOKEN", "")
_CHANGES_DB = os.environ.get("NOTION_CHANGES_DB_ID", "")

_HEADERS = {
    "Authorization": f"Bearer {_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

_BASE = "https://api.notion.com/v1"


# ── Low-level helpers ──────────────────────────────────────────────────────────

def _truncate_for_notion(text: str, limit: int = 2000) -> str:
    """
    Truncate text so it fits within Notion's rich_text length limit.

    Notion counts content length in UTF-16 code units (matching JavaScript's
    String.length), not Unicode code points. Characters outside the BMP
    (emoji, some symbols) take 2 code units each, so Python's str slice of
    2000 chars can exceed Notion's 2000-code-unit limit.

    This helper truncates by encoding to UTF-16 LE, slicing to `limit*2`
    bytes, and decoding back — discarding any half-surrogate at the cut.
    """
    if not text:
        return text
    encoded = text.encode("utf-16-le")
    if len(encoded) <= limit * 2:
        return text
    truncated = encoded[: limit * 2]
    try:
        return truncated.decode("utf-16-le")
    except UnicodeDecodeError:
        # Cut landed mid-surrogate-pair — drop the last code unit and try again
        return truncated[:-2].decode("utf-16-le", errors="ignore")


def _check_status(r: requests.Response, method: str, path: str) -> None:
    """raise_for_status with the Notion error body included in the log."""
    if r.status_code >= 400:
        body_preview = (r.text or "")[:1500]
        logger.error(
            "Notion API %s %s → %d: %s",
            method, path, r.status_code, body_preview,
        )
    r.raise_for_status()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{_BASE}{path}", headers=_HEADERS, json=body, timeout=30)
    _check_status(r, "POST", path)
    return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _patch(path: str, body: dict) -> dict:
    r = requests.patch(f"{_BASE}{path}", headers=_HEADERS, json=body, timeout=30)
    _check_status(r, "PATCH", path)
    return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get(path: str) -> dict:
    r = requests.get(f"{_BASE}{path}", headers=_HEADERS, timeout=30)
    _check_status(r, "GET", path)
    return r.json()


def _query_db(db_id: str, filter_body: dict, sorts: list = None) -> list[dict]:
    """Paginate through all results of a database query."""
    results = []
    cursor = None
    while True:
        body: dict = {"filter": filter_body, "page_size": 100}
        if sorts:
            body["sorts"] = sorts
        if cursor:
            body["start_cursor"] = cursor
        data = _post(f"/databases/{db_id}/query", body)
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


# ── Changes Database ──────────────────────────────────────────────────────────

def change_already_logged(competitor_name: str, url: str, detected_at: str) -> bool:
    """
    Return True if a change for this competitor/URL was already logged within
    a 2-hour window of detected_at. Prevents duplicate entries on overlapping polls.
    """
    if not detected_at:
        return False
    try:
        from datetime import timedelta
        dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
        window_start = (dt - timedelta(hours=1)).isoformat()
        window_end   = (dt + timedelta(hours=1)).isoformat()
        results = _query_db(
            _CHANGES_DB,
            {"and": [
                {"property": "Competitor", "select": {"equals": competitor_name}},
                {"property": "URL",        "url":    {"equals": url}},
                {"property": "Date Detected", "date": {"on_or_after":  window_start}},
                {"property": "Date Detected", "date": {"on_or_before": window_end}},
            ]},
        )
        return len(results) > 0
    except Exception as e:
        logger.debug("Dedup check failed (allowing log): %s", e)
        return False


def log_change(
    competitor_name: str,
    tier: str,
    url: str,
    raw_change: str,
    category: str = "Other",
    source_type: str = "Web",
    detected_at: str = "",
) -> str:
    """Write a new change entry to the Changes database. Returns the new page ID."""
    properties: dict = {
        "Name": {
            "title": [{"text": {"content": f"{competitor_name} — {category} change"}}]
        },
        "Competitor": {"select": {"name": competitor_name}},
        "Tier": {"select": {"name": tier}},
        "URL": {"url": url},
        "Source Type": {"select": {"name": source_type}},
        "Category": {"select": {"name": category}},
        "Raw Change": {"rich_text": [{"text": {"content": _truncate_for_notion(raw_change)}}]},
        "Date Detected": {"date": {"start": detected_at or datetime.now(timezone.utc).isoformat()}},
        "Status": {"select": {"name": "Unscored"}},
        "Teams Alert Sent": {"checkbox": False},
    }

    body = {"parent": {"database_id": _CHANGES_DB}, "properties": properties}
    response = _post("/pages", body)
    page_id = response["id"]
    logger.info("Logged change for %s → page %s", competitor_name, page_id)
    return page_id


def get_unscored_changes() -> list[dict]:
    """Return all change pages with Status = Unscored."""
    return _query_db(
        _CHANGES_DB,
        {"property": "Status", "select": {"equals": "Unscored"}},
    )


def update_change_score(page_id: str, score: int, reasoning: str) -> None:
    _patch(f"/pages/{page_id}", {"properties": {
        "Significance Score": {"number": score},
        "Score Reasoning": {"rich_text": [{"text": {"content": _truncate_for_notion(reasoning)}}]},
        "Status": {"select": {"name": "Scored"}},
    }})
    logger.info("Scored change %s → %d/10", page_id, score)


def update_change_summary(page_id: str, summary: str) -> None:
    _patch(f"/pages/{page_id}", {"properties": {
        "AI Summary": {"rich_text": [{"text": {"content": _truncate_for_notion(summary)}}]},
    }})


def mark_alert_sent(page_id: str) -> None:
    _patch(f"/pages/{page_id}", {"properties": {
        "Teams Alert Sent": {"checkbox": True},
    }})


def get_monthly_changes(year: int, month: int, min_score: int = 0) -> list[dict]:
    """Return all scored changes from a given month, optionally filtered by min score."""
    from calendar import monthrange
    first = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
    last_day = monthrange(year, month)[1]
    last = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc).isoformat()

    conditions = [
        {"property": "Date Detected", "date": {"on_or_after": first}},
        {"property": "Date Detected", "date": {"on_or_before": last}},
        {"property": "Status", "select": {"does_not_equal": "Unscored"}},
    ]
    if min_score > 0:
        conditions.append({
            "property": "Significance Score",
            "number": {"greater_than_or_equal_to": min_score},
        })

    return _query_db(
        _CHANGES_DB,
        {"and": conditions},
        sorts=[{"property": "Significance Score", "direction": "descending"}],
    )


# ── Field extraction helper ───────────────────────────────────────────────────

def extract_change_fields(page: dict) -> dict:
    """Pull relevant fields from a raw Notion page object into a clean dict."""
    props = page.get("properties", {})

    def select_val(key):
        sel = props.get(key, {}).get("select")
        return sel["name"] if sel else ""

    def text_val(key):
        parts = props.get(key, {}).get("rich_text", [])
        return "".join(p.get("plain_text", "") for p in parts)

    def title_val(key):
        parts = props.get(key, {}).get("title", [])
        return "".join(p.get("plain_text", "") for p in parts)

    return {
        "page_id": page["id"],
        "competitor": select_val("Competitor"),
        "tier": select_val("Tier"),
        "category": select_val("Category"),
        "url": props.get("URL", {}).get("url") or "",
        "raw_change": text_val("Raw Change"),
        "ai_summary": text_val("AI Summary"),
        "score": props.get("Significance Score", {}).get("number"),
        "score_reasoning": text_val("Score Reasoning"),
        "status": select_val("Status"),
        "teams_alert_sent": props.get("Teams Alert Sent", {}).get("checkbox", False),
        "date_detected": props.get("Date Detected", {}).get("date", {}).get("start", ""),
    }
