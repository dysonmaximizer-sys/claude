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
# Measured 2026-08-31 on 33 real rows, both models, same prompts:
#   sonnet-4-6  24,000 input / 2,424 output  ->  $1.85/month
#   sonnet-5    33,240 input / 2,831 output  ->  $1.62/month  (12% cheaper)
# The per-token rate is lower ($2/$10 vs $3/$15) but Sonnet 5's newer tokenizer
# turns the same text into ~1.39x more tokens, so most of the rate cut is eaten.
# Sonnet 5 also scores ~0.5 points harsher near the alert boundary: 7 of those 33
# rows crossed the >5 line, 6 of them downward. If alert volume drops noticeably,
# the fix is ALERT_SCORE_THRESHOLD, not the model.
CLAUDE_MODEL = "claude-sonnet-5"
# Cheapest model available, used only for the 1-token startup preflight that
# proves the key can run billed inference (see integrations/anthropic_preflight).
# Credit and spend-limit errors are account-scoped, not model-scoped, so the
# cheap model is a valid proxy for the real one.
PREFLIGHT_MODEL = "claude-haiku-4-5-20251001"

# ── Competitor Registry ───────────────────────────────────────────────────────
# Valid `tier` values, which must match the Notion "Tier" select options exactly:
#   "Tier 1"      direct, highest-priority threats
#   "Tier 2"      relevant but less direct
#   "Ankle Biter" monitor, lower urgency
#   "Frenemies"   partner and competitor at once — integration or partnership news
#                 from these matters as much as their competitive moves.
#                 Currently: Focal AI, Continuum, Zocks, Fireflies.
# NOTE: the tier is passed to the scoring prompt as a bare label ("Tier: Frenemies")
# and the prompt does not explain the vocabulary, so today the value is metadata for
# humans (Teams cards, Notion views, the newsletter) rather than something that
# changes how a change is scored. Making it steer scoring means adding a tier
# glossary to agents/scoring_agent.SYSTEM_PROMPT.
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
            # learn.microsoft.com is a separate host and was being discarded every
            # run (spotted in the 2026-08-28 log). Release notes are high signal.
            ("learn.microsoft.com", "/dynamics365"),
        ],
        "title_patterns": [r"microsoft dynamics", r"\bdynamics 365\b"],
        "slug_match": False,
    },
    # Frenemies — partner and competitor at once. AI meeting-notes and client
    # intelligence assistants that integrate with CRMs (ours included) while
    # absorbing workflows a CRM would otherwise own. Their integration and
    # partnership announcements matter as much as their feature launches.
    # Domains verified 2026-08-31 against each vendor's own site.
    "Focal AI": {
        "tier": "Frenemies",
        "slug": "focal",
        "url_patterns": [
            ("meetwithfocal.com", None),
            ("linkedin.com", "/company/meetwithfocal"),
        ],
        "title_patterns": [r"\bfocal ai\b", r"\bmeetwithfocal\b"],
        # "focal" alone collides with our own demo-engine vocabulary ("focal note")
        "slug_match": False,
    },
    "Continuum": {
        "tier": "Frenemies",
        "slug": "continuum",
        # oncontinuum.com is the AI client-intelligence product used by iA,
        # Manulife Wealth and Sterling Mutuals. Several unrelated advisory firms
        # trade as "Continuum" (continuumadvisory.com, contwealth.com,
        # continuumwealthstrategies.com), so host matching is the only safe route.
        "url_patterns": [("oncontinuum.com", None)],
        "slug_match": False,
    },
    "Zocks": {
        "tier": "Frenemies",
        "slug": "zocks",
        "url_patterns": [
            ("zocks.io", None),
            ("linkedin.com", "/company/zocks"),
        ],
        "title_patterns": [r"\bzocks\b"],
        "slug_match": False,
    },
    "Fireflies": {
        "tier": "Frenemies",
        "slug": "fireflies",
        "url_patterns": [("fireflies.ai", None)],
        "title_patterns": [r"\bfireflies\b"],
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

# Whether re-scoring a backlog row may raise a Teams alert. OFF by policy
# (2026-08-18): backlog rows are days or weeks old by the time they are scored,
# so alerting on them means notifying people about stale news and burying the
# fresh signal. Backlog is scored silently and reaches the team through the
# monthly newsletter; only changes detected in the current run alert.
RESCUE_SWEEP_ALERTS = False

# How many scoring failures the daily poll tolerates before it treats them as
# systemic and fails the run. A failed row is left Unscored, and the next run's
# rescue sweep re-scores it, so a transient blip is self-healing — on 2026-08-28
# one HTTP 500 out of 27 rows turned into a red run plus a daily "PIPELINE
# PROBLEM" card for a fault that lasted one request. A run is called systemic if
# it exceeds this count OR more than half its scoring attempts failed, and a
# genuine outage is still caught within a day by the health check's backlog test.
SCORING_FAILURE_TOLERANCE = 3

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
