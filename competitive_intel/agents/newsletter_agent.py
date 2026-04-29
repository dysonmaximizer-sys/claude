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
import re
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
    Send the newsletter via Resend API with a styled HTML version.
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

    payload = {
        "from": SMTP_FROM,
        "to": NEWSLETTER_RECIPIENTS,
        "subject": subject,
        "text": newsletter_text,
        "html": _render_html(newsletter_text, month_name),
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


# ── HTML Renderer ─────────────────────────────────────────────────────────────

def _render_html(text: str, month_name: str) -> str:
    """Convert plain-text newsletter to a styled HTML email."""

    sections = _parse_sections(text)

    html_sections = ""

    # Executive Summary
    if "EXECUTIVE SUMMARY" in sections:
        html_sections += _section(
            title="Executive Summary",
            accent="#1B3A6B",
            content=_paragraphs(sections["EXECUTIVE SUMMARY"]),
        )

    # Top Signals
    if "TOP SIGNALS THIS MONTH" in sections:
        html_sections += _section(
            title="Top Signals This Month",
            accent="#1B3A6B",
            content=_render_signals(sections["TOP SIGNALS THIS MONTH"]),
        )

    # Watch List
    if "WATCH LIST" in sections:
        html_sections += _section(
            title="Watch List",
            accent="#1B3A6B",
            content=_render_watchlist(sections["WATCH LIST"]),
        )

    # Market Themes
    if "MARKET THEMES" in sections:
        html_sections += _section(
            title="Market Themes",
            accent="#1B3A6B",
            content=_render_bullets(sections["MARKET THEMES"]),
        )

    # Implications by Team
    if "IMPLICATIONS BY TEAM" in sections:
        html_sections += _section(
            title="Implications by Team",
            accent="#1B3A6B",
            content=_render_implications(sections["IMPLICATIONS BY TEAM"]),
        )

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, minimum-scale=1, maximum-scale=1">
  <style type="text/css">
    body, p, div, td {{ font-family: arial, helvetica, sans-serif; font-size: 14px; color: #000000; }}
    body {{ margin: 0; padding: 0; background-color: #f4f4f4; }}
    p {{ margin: 0; padding: 0; }}
    a {{ color: #1188E6; text-decoration: none; }}
    h2 {{ margin: 0; padding: 0; }}
  </style>
</head>
<body>
  <table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f4f4f4">
    <tr>
      <td align="center" style="padding: 24px 0;">
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px; width:100%;" bgcolor="#ffffff">

          <!-- Header -->
          <tr>
            <td bgcolor="#1B3A6B" style="padding: 28px 32px 24px 32px;">
              <p style="font-size: 11px; color: #8BADD4; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px;">Maximizer Competitive Intelligence</p>
              <h1 style="font-family: arial, helvetica, sans-serif; font-size: 22px; font-weight: bold; color: #ffffff; margin: 0 0 6px 0; line-height: 1.3;">Monthly Strategic Synthesis</h1>
              <p style="font-size: 14px; color: #8BADD4; margin: 0;">{month_name}</p>
            </td>
          </tr>

          <!-- Body sections -->
          {html_sections}

          <!-- Divider -->
          <tr>
            <td style="padding: 0 32px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr><td height="1" bgcolor="#E0E5E5" style="font-size:1px; line-height:1px;">&nbsp;</td></tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px 28px 32px; text-align: center;">
              <p style="font-size: 12px; color: #888888; line-height: 1.6;">
                <strong style="color: #343738;">Maximizer Services Inc.</strong><br>
                Unit 260-60 Smithe St, Vancouver, BC V6B 0P5 Canada<br>
                This report is for internal use only.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _parse_sections(text: str) -> dict:
    """Split plain-text newsletter into named sections."""
    section_names = [
        "EXECUTIVE SUMMARY",
        "TOP SIGNALS THIS MONTH",
        "WATCH LIST",
        "MARKET THEMES",
        "IMPLICATIONS BY TEAM",
    ]
    sections = {}
    pattern = "(" + "|".join(re.escape(s) for s in section_names) + ")"
    parts = re.split(pattern, text)

    current = None
    for part in parts:
        if part in section_names:
            current = part
            sections[current] = ""
        elif current:
            sections[current] = part.strip()

    return sections


def _section(title: str, accent: str, content: str) -> str:
    """Wrap content in a standard section block."""
    return f"""
          <tr>
            <td style="padding: 28px 32px 0 32px;">
              <h2 style="font-family: arial, helvetica, sans-serif; font-size: 18px; font-weight: bold;
                         color: {accent}; margin: 0 0 14px 0; padding-bottom: 8px;
                         border-bottom: 2px solid #E8EDF5;">
                {title}
              </h2>
              {content}
            </td>
          </tr>
          <tr><td style="padding: 20px 0 0 0;"></td></tr>"""


def _paragraphs(text: str) -> str:
    """Render plain text as HTML paragraphs."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(
        f'<p style="line-height: 1.7; color: #333333; margin-bottom: 10px;">{_escape(p)}</p>'
        for p in paras
    )


def _render_signals(text: str) -> str:
    """Render Top Signals section — score-badged cards."""
    if not text.strip() or "no competitor changes" in text.lower():
        return '<p style="color: #666666; font-style: italic;">No changes scored 7 or above this month.</p>'

    lines = text.strip().splitlines()
    out = ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Detect a signal entry: • Competitor | Category | Score: X/10
        if line.startswith(("•", "-", "*")) and "|" in line and "Score" in line:
            header = line.lstrip("•-* ").strip()
            parts = [p.strip() for p in header.split("|")]
            competitor = parts[0] if len(parts) > 0 else ""
            category   = parts[1] if len(parts) > 1 else ""
            score_text = parts[2] if len(parts) > 2 else ""
            score_num  = re.search(r"(\d+)", score_text)
            score      = int(score_num.group(1)) if score_num else 0
            badge_color = "#C0392B" if score >= 8 else "#E67E22"

            body_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(("•", "-", "*")):
                body_lines.append(lines[i].strip())
                i += 1

            body_html = "".join(
                f'<p style="line-height:1.6; color:#333333; margin: 4px 0;">{_format_signal_line(l)}</p>'
                for l in body_lines if l
            )

            out += f"""
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 14px;">
                <tr>
                  <td style="background-color: #F7F9FC; border-left: 4px solid {badge_color};
                              padding: 14px 16px; border-radius: 2px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td>
                          <span style="font-size:13px; font-weight:bold; color:#1B3A6B;">{_escape(competitor)}</span>
                          <span style="font-size:12px; color:#666666; margin: 0 6px;">|</span>
                          <span style="font-size:12px; color:#555555;">{_escape(category)}</span>
                        </td>
                        <td align="right">
                          <span style="background-color:{badge_color}; color:#ffffff; font-size:11px;
                                       font-weight:bold; padding: 3px 8px; border-radius: 10px;">
                            {score}/10
                          </span>
                        </td>
                      </tr>
                    </table>
                    <div style="margin-top: 8px;">{body_html}</div>
                  </td>
                </tr>
              </table>"""
        else:
            if line:
                out += f'<p style="line-height:1.7; color:#333333; margin-bottom:8px;">{_escape(line)}</p>'
            i += 1

    return out or '<p style="color:#666666; font-style:italic;">No changes scored 7 or above this month.</p>'


def _render_watchlist(text: str) -> str:
    """Render Watch List section — compact score-tagged rows."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return '<p style="color:#666666; font-style:italic;">No changes in the 5–6 range this month.</p>'

    out = ""
    for line in lines:
        line = line.lstrip("•-* ").strip()
        if not line:
            continue

        # Try to extract score badge
        score_match = re.search(r"Score[:\s]+(\d+)/10", line, re.IGNORECASE)
        score = int(score_match.group(1)) if score_match else None

        badge = ""
        if score:
            badge = f'<span style="background-color:#F39C12; color:#ffffff; font-size:11px; font-weight:bold; padding:2px 7px; border-radius:10px; margin-left:8px;">{score}/10</span>'
            line = re.sub(r"\|?\s*Score[:\s]+\d+/10", "", line, flags=re.IGNORECASE).strip().rstrip("|").strip()

        out += f"""
          <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:8px;">
            <tr>
              <td style="padding: 10px 14px; border-left: 3px solid #F39C12; background-color:#FFFBF0;">
                <span style="font-size:13px; color:#333333; line-height:1.6;">{_escape(line)}</span>{badge}
              </td>
            </tr>
          </table>"""

    return out


def _render_bullets(text: str) -> str:
    """Render Market Themes as styled bullet points."""
    lines = [l.strip().lstrip("•-* ") for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return ""

    items = "".join(
        f"""<tr>
              <td width="16" valign="top" style="padding: 3px 8px 8px 0; color:#1B3A6B; font-weight:bold; font-size:16px; line-height:1.4;">&#8226;</td>
              <td style="padding-bottom:8px; line-height:1.7; color:#333333;">{_escape(l)}</td>
            </tr>"""
        for l in lines if l
    )
    return f'<table cellpadding="0" cellspacing="0" border="0" width="100%">{items}</table>'


def _render_implications(text: str) -> str:
    """Render Implications by Team with team-coloured labels."""
    team_colors = {
        "Sales":     "#27AE60",
        "Product":   "#1188E6",
        "Marketing": "#8E44AD",
    }
    lines = text.strip().splitlines()
    out = ""
    for line in lines:
        line = line.strip().lstrip("→>- ").strip()
        if not line:
            continue
        matched = False
        for team, color in team_colors.items():
            if line.lower().startswith(team.lower()):
                body = re.sub(rf"^{team}\s*[:\-]?\s*", "", line, flags=re.IGNORECASE)
                out += f"""
          <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:10px;">
            <tr>
              <td style="padding:12px 16px; background-color:#F7F9FC; border-left:4px solid {color};">
                <span style="font-size:12px; font-weight:bold; color:{color}; text-transform:uppercase;
                             letter-spacing:1px;">{team}</span>
                <p style="margin:4px 0 0 0; line-height:1.7; color:#333333;">{_escape(body)}</p>
              </td>
            </tr>
          </table>"""
                matched = True
                break
        if not matched and line:
            out += f'<p style="line-height:1.7; color:#333333; margin-bottom:8px;">{_escape(line)}</p>'

    return out


def _format_signal_line(line: str) -> str:
    """Bold the label prefix (What:, Why it matters:, Recommended action:) in signal body lines."""
    match = re.match(r"^(What|Why it matters|Recommended action)\s*:", line, re.IGNORECASE)
    if match:
        label = match.group(0)
        rest = line[len(label):].strip()
        return f"<strong>{_escape(label)}</strong> {_escape(rest)}"
    return _escape(line)


def _escape(text: str) -> str:
    """HTML-escape a string."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


# ── Prompt helpers ────────────────────────────────────────────────────────────

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
