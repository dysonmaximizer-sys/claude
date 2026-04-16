"""
Notion integration — single source of truth for all competitor changes.

Databases managed here:
  - Competitors: one row per competitor, links to battlecard page
  - Changes: every detected change, with score, summary, and distribution status
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from notion_client import Client
from tenacity import retry, stop_after_attempt, wait_exponential

from config import NOTION_TOKEN, NOTION_COMPETITORS_DB_ID, NOTION_CHANGES_DB_ID

logger = logging.getLogger(__name__)
notion = Client(auth=NOTION_TOKEN)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_text(blocks: list) -> str:
    """Extract plain text from a Notion rich_text property."""
    return "".join(b.get("plain_text", "") for b in blocks)


# ── Changes Database ──────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def log_change(
    competitor_name: str,
    tier: str,
    url: str,
    raw_change: str,
    category: str = "Other",
    source_type: str = "Web",
) -> str:
    """
    Write a new change entry to the Changes database.
    Returns the new page ID.
    """
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

    if competitor_page_id:
        properties["Competitor Page"] = {"relation": [{"id": competitor_page_id}]}

    response = notion.pages.create(
        parent={"database_id": NOTION_CHANGES_DB_ID},
        properties=properties,
    )
    page_id = response["id"]
    logger.info("Logged change for %s → page %s", competitor_name, page_id)
    return page_id


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_unscored_changes() -> list[dict]:
    """Return all change pages with Status = Unscored."""
    results = []
    cursor = None

    while True:
        kwargs: dict = {
            "database_id": NOTION_CHANGES_DB_ID,
            "filter": {"property": "Status", "select": {"equals": "Unscored"}},
        }
        if cursor:
            kwargs["start_cursor"] = cursor

        response = notion.databases.query(**kwargs)
        results.extend(response["results"])

        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]

    return results


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def update_change_score(page_id: str, score: int, reasoning: str) -> None:
    """Write the significance score and reasoning back to a change page."""
    notion.pages.update(
        page_id=page_id,
        properties={
            "Significance Score": {"number": score},
            "Score Reasoning": {"rich_text": [{"text": {"content": reasoning[:2000]}}]},
            "Status": {"select": {"name": "Scored"}},
        },
    )
    logger.info("Scored change %s → %d/10", page_id, score)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def update_change_summary(page_id: str, summary: str) -> None:
    """Write the AI-generated summary to a change page."""
    notion.pages.update(
        page_id=page_id,
        properties={
            "AI Summary": {"rich_text": [{"text": {"content": summary[:2000]}}]},
        },
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def mark_alert_sent(page_id: str) -> None:
    notion.pages.update(
        page_id=page_id,
        properties={"Teams Alert Sent": {"checkbox": True}},
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def mark_battlecard_updated(page_id: str) -> None:
    notion.pages.update(
        page_id=page_id,
        properties={"Battlecard Updated": {"checkbox": True}},
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_monthly_changes(year: int, month: int, min_score: int = 0) -> list[dict]:
    """Return all scored changes from a given month, optionally filtered by min score."""
    from calendar import monthrange
    first = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
    last_day = monthrange(year, month)[1]
    last = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc).isoformat()

    filters: list = [
        {"property": "Date Detected", "date": {"on_or_after": first}},
        {"property": "Date Detected", "date": {"on_or_before": last}},
        {"property": "Status", "select": {"does_not_equal": "Unscored"}},
    ]
    if min_score > 0:
        filters.append({"property": "Significance Score", "number": {"greater_than_or_equal_to": min_score}})

    results = []
    cursor = None

    while True:
        kwargs: dict = {
            "database_id": NOTION_CHANGES_DB_ID,
            "filter": {"and": filters},
            "sorts": [{"property": "Significance Score", "direction": "descending"}],
        }
        if cursor:
            kwargs["start_cursor"] = cursor

        response = notion.databases.query(**kwargs)
        results.extend(response["results"])

        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]

    return results


# ── Competitors Database ──────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_competitor_page_id(competitor_name: str) -> Optional[str]:
    """Look up a competitor's Notion page ID by name."""
    response = notion.databases.query(
        database_id=NOTION_COMPETITORS_DB_ID,
        filter={"property": "Name", "title": {"equals": competitor_name}},
    )
    if response["results"]:
        return response["results"][0]["id"]
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_battlecard_page_id(competitor_name: str) -> Optional[str]:
    """Return the battlecard Notion page ID linked to a competitor."""
    comp_page_id = get_competitor_page_id(competitor_name)
    if not comp_page_id:
        return None

    page = notion.pages.retrieve(comp_page_id)
    battlecard_prop = page["properties"].get("Battlecard Page", {})
    relations = battlecard_prop.get("relation", [])
    if relations:
        return relations[0]["id"]
    return None


def extract_change_fields(page: dict) -> dict:
    """
    Pull the relevant fields out of a raw Notion page object
    into a clean dict for use by agents.
    """
    props = page["properties"]

    def select_val(key: str) -> str:
        sel = props.get(key, {}).get("select")
        return sel["name"] if sel else ""

    def text_val(key: str) -> str:
        return _safe_text(props.get(key, {}).get("rich_text", []))

    def number_val(key: str) -> Optional[int]:
        return props.get(key, {}).get("number")

    def url_val(key: str) -> str:
        return props.get(key, {}).get("url") or ""

    return {
        "page_id": page["id"],
        "competitor": select_val("Competitor"),
        "tier": select_val("Tier"),
        "category": select_val("Category"),
        "url": url_val("URL"),
        "raw_change": text_val("Raw Change"),
        "ai_summary": text_val("AI Summary"),
        "score": number_val("Significance Score"),
        "score_reasoning": text_val("Score Reasoning"),
        "status": select_val("Status"),
        "teams_alert_sent": props.get("Teams Alert Sent", {}).get("checkbox", False),
        "battlecard_updated": props.get("Battlecard Updated", {}).get("checkbox", False),
        "date_detected": props.get("Date Detected", {}).get("date", {}).get("start", ""),
    }
