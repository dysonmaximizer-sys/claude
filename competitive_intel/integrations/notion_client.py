"""
Notion integration — single source of truth for all competitor changes.

Uses raw HTTP requests throughout to avoid notion-client version incompatibilities.

Databases managed here:
  - Competitors: one row per competitor, links to battlecard page
  - Changes: every detected change, with score, summary, and distribution status
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Loaded directly from env (config.py imports us, so avoid circular import)
_TOKEN = os.environ.get("NOTION_TOKEN", "")
_COMPETITORS_DB = os.environ.get("NOTION_COMPETITORS_DB_ID", "")
_CHANGES_DB = os.environ.get("NOTION_CHANGES_DB_ID", "")

_HEADERS = {
    "Authorization": f"Bearer {_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

_BASE = "https://api.notion.com/v1"


# ── Low-level helpers ──────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{_BASE}{path}", headers=_HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _patch(path: str, body: dict) -> dict:
    r = requests.patch(f"{_BASE}{path}", headers=_HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get(path: str) -> dict:
    r = requests.get(f"{_BASE}{path}", headers=_HEADERS, timeout=30)
    r.raise_for_status()
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

def log_change(
    competitor_name: str,
    tier: str,
    url: str,
    raw_change: str,
    category: str = "Other",
    source_type: str = "Web",
) -> str:
    """Write a new change entry to the Changes database. Returns the new page ID."""
    competitor_page_id = get_competitor_page_id(competitor_name)

    properties: dict = {
        "Name": {
            "title": [{"text": {"content": f"{competitor_name} — {category} change"}}]
        },
        "Competitor": {"select": {"name": competitor_name}},
        "Tier": {"select": {"name": tier}},
        "URL": {"url": url},
        "Source Type": {"select": {"name": source_type}},
        "Category": {"select": {"name": category}},
        "Raw Change": {"rich_text": [{"text": {"content": raw_change[:2000]}}]},
        "Date Detected": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
        "Status": {"select": {"name": "Unscored"}},
        "Teams Alert Sent": {"checkbox": False},
        "Battlecard Updated": {"checkbox": False},
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
        "Score Reasoning": {"rich_text": [{"text": {"content": reasoning[:2000]}}]},
        "Status": {"select": {"name": "Scored"}},
    }})
    logger.info("Scored change %s → %d/10", page_id, score)


def update_change_summary(page_id: str, summary: str) -> None:
    _patch(f"/pages/{page_id}", {"properties": {
        "AI Summary": {"rich_text": [{"text": {"content": summary[:2000]}}]},
    }})


def mark_alert_sent(page_id: str) -> None:
    _patch(f"/pages/{page_id}", {"properties": {
        "Teams Alert Sent": {"checkbox": True},
    }})


def mark_battlecard_updated(page_id: str) -> None:
    _patch(f"/pages/{page_id}", {"properties": {
        "Battlecard Updated": {"checkbox": True},
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


# ── Competitors Database ──────────────────────────────────────────────────────

def get_competitor_page_id(competitor_name: str) -> Optional[str]:
    """Look up a competitor's Notion page ID by name."""
    if not _COMPETITORS_DB:
        return None
    results = _query_db(
        _COMPETITORS_DB,
        {"property": "Name", "title": {"equals": competitor_name}},
    )
    return results[0]["id"] if results else None


def get_battlecard_page_id(competitor_name: str) -> Optional[str]:
    """Return the battlecard Notion page ID linked to a competitor."""
    comp_page_id = get_competitor_page_id(competitor_name)
    if not comp_page_id:
        return None
    page = _get(f"/pages/{comp_page_id}")
    relations = page.get("properties", {}).get("Battlecard Page", {}).get("relation", [])
    return relations[0]["id"] if relations else None


# ── Block operations (used by battlecard_updater) ─────────────────────────────

def append_blocks(page_id: str, children: list) -> None:
    _post(f"/blocks/{page_id}/children", {"children": children})


def get_block_children(page_id: str) -> list:
    data = _get(f"/blocks/{page_id}/children")
    return data.get("results", [])


def update_block(block_id: str, block_type: str, content: dict) -> None:
    _patch(f"/blocks/{block_id}", {block_type: content})


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
        "battlecard_updated": props.get("Battlecard Updated", {}).get("checkbox", False),
        "date_detected": props.get("Date Detected", {}).get("date", {}).get("start", ""),
    }
