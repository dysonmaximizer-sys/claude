"""
Newsletter agent — generates the monthly Strategic Synthesis newsletter.

Runs on the 1st of each month. Synthesises all scored changes from the previous
month into a structured executive briefing, then:
  1. Saves the full newsletter to output/
  2. Posts an announcement + preview to the Teams general channel
  3. Emails the full newsletter to the configured recipient list

Uses prompt caching on the system prompt.
"""

import logging
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import requests

import anthropic

from config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    RESEND_API_KEY,
    SMTP_FROM,
    NEWSLETTER_RECIPIENTS,
)

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are writing the monthly Competitive Intelligence Strategic Synthesis \
for Maximizer's senior leadership team. Maximizer is a B2B SaaS CRM for wealth management \
and insurance advisory firms.

Your newsletter must follow this exact structure:

---
COMPETITIVE INTELLIGENCE: MONTHLY STRATEGIC SYNTHESIS
[Month Year]

EXECUTIVE SUMMARY
2–3 sentences on the most important competitive development this month and its strategic implication.

TOP SIGNALS THIS MONTH
For each significant change (score ≥ 7), write one entry:
  • [Competitor] | [Category] | Score: X/10
    What: <one sentence>
    Why it matters: <one sentence>
    Recommended action: <one sentence>

WATCH LIST
Changes scored 5–6: briefer entries (competitor, category, one-line note).

MARKET THEMES
2–3 bullet points identifying patterns across competitors (e.g. "Three Tier 1 competitors added AI features this month").

IMPLICATIONS BY TEAM
  → Sales: <1–2 sentences of talk track guidance>
  → Product: <1–2 sentences on feature prioritisation signals>
  → Marketing: <1–2 sentences on GTM adjustments>
---

Write in executive-friendly language: punchy, direct, no jargon. \
Total length: 400–600 words."""


def generate_newsletter(changes: list[dict], month: int, year: int) -> str:
    """
    Generate the monthly Strategic Synthesis from a list of scored change dicts.

    Each change dict should have keys: competitor, tier, category, score,
    ai_summary, score_reasoning, url, date_detected.

    Returns the newsletter as a plain text string.
    """
    if not changes:
        return _empty_newsletter(month, year)

    # Build a structured summary of this month's changes for the prompt
    changes_text = _format_changes_for_prompt(changes)

    month_name = datetime(year, month, 1).strftime("%B %Y")

    user_content = f"""Generate the Strategic Synthesis newsletter for {month_name}.

This month's competitive changes ({len(changes)} total):

{changes_text}

Write the full newsletter now."""

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        return message.content[0].text.strip()

    except anthropic.APIError as e:
        logger.error("Anthropic API error during newsletter generation: %s", e)
        raise


def save_newsletter(newsletter_text: str, month: int, year: int) -> Path:
    """Save the newsletter to the output/ directory."""
    output_dir = Path(__file__).parent.parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    month_name = datetime(year, month, 1).strftime("%Y-%m")
    file_path = output_dir / f"competitive_intel_newsletter_{month_name}.txt"
    file_path.write_text(newsletter_text, encoding="utf-8")
    logger.info("Newsletter saved to %s", file_path)
    return file_path


def email_newsletter(newsletter_text: str, month: int, year: int) -> bool:
    """
    Send the newsletter via Resend API (HTTPS).
    Returns True on success, False if not configured.
    """
    if not RESEND_API_KEY:
        logger.warning(
            "Resend API key not configured — email skipped. "
            "Add RESEND_API_KEY to .env to enable email delivery."
        )
        return False

    month_name = datetime(year, month, 1).strftime("%B %Y")
    subject = f"Competitive Intelligence: Monthly Strategic Synthesis — {month_name}"
    html_body = (
        f"<html><body>"
        f"<pre style='font-family:Arial,sans-serif;font-size:14px;line-height:1.6'>"
        f"{newsletter_text}"
        f"</pre></body></html>"
    )

    payload = {
        "from": SMTP_FROM,
        "to": NEWSLETTER_RECIPIENTS,
        "subject": subject,
        "text": newsletter_text,
        "html": html_body,
    }

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        logger.info("Newsletter emailed to: %s", ", ".join(NEWSLETTER_RECIPIENTS))
        return True
    except requests.HTTPError as e:
        logger.error("Resend API error: %s — %s", e, response.text)
        return False
    except requests.RequestException as e:
        logger.error("Failed to send newsletter email: %s", e)
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_changes_for_prompt(changes: list[dict]) -> str:
    lines = []
    for c in changes:
        lines.append(
            f"- {c['competitor']} ({c['tier']}) | {c['category']} | Score: {c.get('score', '?')}/10\n"
            f"  Summary: {c.get('ai_summary') or c.get('raw_change', '')[:200]}\n"
            f"  URL: {c.get('url', '')}"
        )
    return "\n\n".join(lines)


def _empty_newsletter(month: int, year: int) -> str:
    month_name = datetime(year, month, 1).strftime("%B %Y")
    return textwrap.dedent(f"""
        COMPETITIVE INTELLIGENCE: MONTHLY STRATEGIC SYNTHESIS
        {month_name}

        No significant competitive changes were detected this month.
        All monitored competitor pages remained stable.
    """).strip()
