"""
Central configuration. All secrets are loaded from environment variables.
Never hardcode credentials here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
VISUALPING_API_KEY = os.environ["VISUALPING_API_KEY"]

# ── Notion Database IDs (populated after running setup_notion.py) ─────────────
NOTION_COMPETITORS_DB_ID = os.environ.get("NOTION_COMPETITORS_DB_ID", "")
NOTION_CHANGES_DB_ID = os.environ.get("NOTION_CHANGES_DB_ID", "")
NOTION_PARENT_PAGE_ID = os.environ["NOTION_PARENT_PAGE_ID"]

# ── MS Teams (add webhook URLs once channels are created) ─────────────────────
# General competitive updates channel
TEAMS_GENERAL_WEBHOOK = os.environ.get("TEAMS_GENERAL_WEBHOOK", "")
# Per-competitor webhooks — add keys as TEAMS_WEBHOOK_<COMPETITOR_SLUG>
# e.g. TEAMS_WEBHOOK_EQUISOFT, TEAMS_WEBHOOK_HUBSPOT, etc.

# ── Email (newsletter distribution) ───────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "onboarding@resend.dev")
NEWSLETTER_RECIPIENTS = [
    e.strip()
    for e in os.environ.get("NEWSLETTER_RECIPIENTS", "marketing@maximizer.com").split(",")
    if e.strip()
]

# ── AI Model ──────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"

# ── Competitor Registry ───────────────────────────────────────────────────────
COMPETITORS = {
    # Tier 1 — direct, highest-priority threats
    "Equisoft": {"tier": "Tier 1", "slug": "equisoft"},
    "Cloven":   {"tier": "Tier 1", "slug": "cloven"},
    "HubSpot":  {"tier": "Tier 1", "slug": "hubspot"},
    # Tier 2 — relevant but less direct
    "Laylah":     {"tier": "Tier 2", "slug": "laylah"},
    "Salesforce": {"tier": "Tier 2", "slug": "salesforce"},
    "Wealthbox":  {"tier": "Tier 2", "slug": "wealthbox"},
    "Monday":     {"tier": "Tier 2", "slug": "monday"},
    "Zoho":       {"tier": "Tier 2", "slug": "zoho"},
    # Ankle biters — monitor but lower urgency
    "Onevest":   {"tier": "Ankle Biter", "slug": "onevest"},
    "Pipedrive": {"tier": "Ankle Biter", "slug": "pipedrive"},
    "Advora":    {"tier": "Ankle Biter", "slug": "advora"},
}

# Significance score threshold for triggering alerts and summaries
ALERT_SCORE_THRESHOLD = 5

# Scoring reference: what each band means
SCORE_GUIDE = """
1–2: Cosmetic change (typo fix, minor copy tweak) — log only
3–4: Minor update (small feature note, navigation change) — log only
5–6: Moderate signal (new feature announcement, pricing page restructure, new positioning language)
7–8: High-impact signal (major pricing change, new product tier, direct attack on our differentiators)
9–10: Critical signal (new product launch, funding announcement, direct head-to-head messaging vs us)
"""
