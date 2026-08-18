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
CHANGEDETECTION_API_KEY = os.environ["CHANGEDETECTION_API_KEY"]
CHANGEDETECTION_BASE_URL = os.environ["CHANGEDETECTION_BASE_URL"]

# ── Notion Database IDs (populated after running setup_notion.py) ─────────────
NOTION_CHANGES_DB_ID = os.environ.get("NOTION_CHANGES_DB_ID", "")
NOTION_PARENT_PAGE_ID = os.environ["NOTION_PARENT_PAGE_ID"]

# ── MS Teams ──────────────────────────────────────────────────────────────────
# Single destination for every alert. Per-competitor webhook routing was removed
# (2026-08-18): all 11 TEAMS_WEBHOOK_<COMPETITOR> secrets were null in the
# workflow, so every alert already fell through to the general webhook while the
# code, YAML, and docs still implied 11 live channels. The competitor name is
# now the headline of every card so one channel stays readable.
TEAMS_GENERAL_WEBHOOK = os.environ.get("TEAMS_GENERAL_WEBHOOK", "")

# ── Email (newsletter distribution) ───────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "onboarding@resend.dev")
# Resend Audience (Segment) ID for the "CI Newsletter" audience — used by
# --mode broadcast to send via Resend's Broadcasts API.
RESEND_AUDIENCE_ID = os.environ.get("RESEND_AUDIENCE_ID", "")
# Single reviewer who receives the draft email under --mode draft for eye-check
# before broadcast.
DRAFT_REVIEWER = os.environ.get("DRAFT_REVIEWER", "lewisdyson@maximizer.com")
# NEWSLETTER_RECIPIENTS is retained only for the old code path during the
# migration window. The new --mode draft path uses DRAFT_REVIEWER instead;
# --mode broadcast uses RESEND_AUDIENCE_ID. Safe to remove once nothing
# else imports NEWSLETTER_RECIPIENTS.
NEWSLETTER_RECIPIENTS = [
    e.strip()
    for e in os.environ.get("NEWSLETTER_RECIPIENTS", "marketing@maximizer.com").split(",")
    if e.strip()
]

# ── AI Model ──────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"
# Cheapest model available, used only for the 1-token startup preflight that
# proves the key can run billed inference (see integrations/anthropic_preflight).
# Credit and spend-limit errors are account-scoped, not model-scoped, so the
# cheap model is a valid proxy for the real one.
PREFLIGHT_MODEL = "claude-haiku-4-5-20251001"

# ── Competitor Registry ───────────────────────────────────────────────────────
# Matching contract (see integrations/changedetection_client._match_competitor):
#   url_patterns   — list of (host_suffix, path_substring_or_None). Matched
#                    against the watch URL's host and path. Precise, so this is
#                    tried first; the most specific pattern wins.
#   title_patterns — list of regexes matched against the watch title, for
#                    watches whose URL doesn't carry the brand (e.g. a LinkedIn
#                    showcase page).
#   slug_match     — legacy fallback: True means "slug appearing anywhere in
#                    title+url is a match". Left on for the original 11
#                    competitors so their existing watches keep matching. It is
#                    OFF for competitors whose slug is a common substring
#                    ("act" would match contact, interact, practifi…), which
#                    rely on url_patterns/title_patterns instead.
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
    "Redtail": {
        "tier": "Tier 2",
        "slug": "redtail",
        # Host-suffix matching covers support.redtailtechnology.com and any
        # other subdomain; both are listed for readability.
        "url_patterns": [
            ("redtailtechnology.com", None),
            ("support.redtailtechnology.com", None),
        ],
        "title_patterns": [r"\bredtail\b"],
        "slug_match": False,
    },
    "AdvisorEngine": {
        "tier": "Tier 2",
        "slug": "advisorengine",
        "url_patterns": [("advisorengine.com", None)],  # includes /newsroom
        "title_patterns": [r"\badvisorengine\b"],
        "slug_match": False,
    },
    "Microsoft Dynamics": {
        "tier": "Tier 2",
        "slug": "microsoft-dynamics",
        # microsoft.com alone is far too broad, so the path is required.
        "url_patterns": [
            ("microsoft.com", "/dynamics-365"),
            ("linkedin.com", "/showcase/microsoft-dynamics"),
        ],
        "title_patterns": [r"microsoft dynamics", r"\bdynamics 365\b"],
        "slug_match": False,
    },
    # Ankle biters — monitor but lower urgency
    "Onevest":   {"tier": "Ankle Biter", "slug": "onevest"},
    "Pipedrive": {"tier": "Ankle Biter", "slug": "pipedrive"},
    "Advora":    {"tier": "Ankle Biter", "slug": "advora"},
    "Act!": {
        "tier": "Tier 2",
        "slug": "act",
        "url_patterns": [("act.com", None)],
        "title_patterns": [r"\bact!"],
        "slug_match": False,  # "act" matches contact, interact, practifi, …
    },
}

# Significance score threshold for triggering alerts and summaries.
# Alerts fire on score > threshold (i.e. 6+), matching the original
# `if score <= ALERT_SCORE_THRESHOLD: skip` behaviour.
ALERT_SCORE_THRESHOLD = 5

# Max stranded ("Unscored") rows the daily poll re-scores at the start of each
# run. Bounded so the rescue sweep can't blow the workflow's 15-minute timeout;
# a larger backlog drains over consecutive runs, or in one pass via
# `python3 -m jobs.backfill_rescore`.
RESCUE_SWEEP_LIMIT = 20

# Alert-worthy rows per Teams digest card. Keeps a batched digest inside Teams'
# payload size limit and bounds how much is lost if a run dies mid-flush.
DIGEST_CHUNK_SIZE = 12

# Scoring reference: what each band means
SCORE_GUIDE = """
1–2: Cosmetic change (typo fix, minor copy tweak) — log only
3–4: Minor update (small feature note, navigation change) — log only
5–6: Moderate signal (new feature announcement, pricing page restructure, new positioning language)
7–8: High-impact signal (major pricing change, new product tier, direct attack on our differentiators)
9–10: Critical signal (new product launch, funding announcement, direct head-to-head messaging vs us)
"""
