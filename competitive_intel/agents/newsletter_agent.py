"""
Newsletter agent — generates the monthly Competitive Intelligence newsletter.

Runs on the 1st of each month. Synthesises all scored changes from the previous
month into a structured briefing, then:
  1. Saves the full newsletter to output/
  2. Posts an announcement + preview to the Teams general channel
  3. Emails the full newsletter to the configured recipient list

The system prompt is loaded from resources/newsletter_system_prompt.txt.
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

# ── System prompt: loaded from resources file ─────────────────────────────────

_PROMPT_FILE = Path(__file__).parent.parent / "resources" / "newsletter_system_prompt.txt"

def _load_system_prompt() -> str:
    try:
        return _PROMPT_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning("newsletter_system_prompt.txt not found at %s — using inline fallback", _PROMPT_FILE)
        return (
            "You are writing a competitive intelligence newsletter for Maximizer CRM. "
            "Use plain text only (no markdown). Section headers must be: "
            "INTRODUCTION, COMPETITIVE NEWS, PRODUCT UPDATES."
        )

SYSTEM_PROMPT = _load_system_prompt()


# ── Newsletter generation ─────────────────────────────────────────────────────

def generate_newsletter(changes: list[dict], month: int, year: int) -> str:
    """
    Generate the monthly newsletter from a list of scored change dicts.

    Each change dict should have keys: competitor, tier, category, score,
    ai_summary, score_reasoning, url, date_detected.

    Returns the newsletter as a plain text string.
    """
    if not changes:
        return _empty_newsletter(month, year)

    changes_text = _format_changes_for_prompt(changes)
    month_name = datetime(year, month, 1).strftime("%B %Y")

    user_content = f"""Generate the competitive intelligence newsletter for {month_name}.

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
    subject = f"Competitive Intelligence: {month_name}"

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

BANNER_URL = "https://www.maximizer.com/wp-content/uploads/2026/04/header_banner.png"

_SOCIAL_ICONS = [
    ("https://www.facebook.com/MaximizerCRM",
     "http://cdn.mcauto-images-production.sendgrid.net/34700707d6c99993/89bece8c-7fe7-44ca-b0ec-a79ca93169dc/24x24.png",
     "Facebook"),
    ("https://www.linkedin.com/company/maximizer-software",
     "http://cdn.mcauto-images-production.sendgrid.net/34700707d6c99993/16481162-a5f0-411d-824d-99dea05652c3/24x24.png",
     "LinkedIn"),
    ("https://twitter.com/MaximizerCRM",
     "http://cdn.mcauto-images-production.sendgrid.net/34700707d6c99993/74afae1d-c53a-4668-a6af-683b68498f1e/25x24.png",
     "Twitter"),
    ("https://www.instagram.com/maximizercrm",
     "http://cdn.mcauto-images-production.sendgrid.net/34700707d6c99993/51ce28c9-bd45-419b-9488-d66326208f10/24x24.png",
     "Instagram"),
]

_MAXIMIZER_LOGO = (
    "http://cdn.mcauto-images-production.sendgrid.net/34700707d6c99993"
    "/e1bdfc53-8897-4d7d-90d0-8ebd6de73a71/472x72.png"
)


def _render_html(text: str, month_name: str) -> str:
    """Convert plain-text newsletter to a styled HTML email matching Maximizer's template."""
    sections = _parse_sections(text)
    body_html = _build_body(sections, month_name)

    social_tds = "".join(
        f"""<td style="padding:0px 5px;">
              <a href="{url}" target="_blank"
                 style="display:inline-block; background-color:transparent; height:21px; width:21px;">
                <img alt="{name}" title="{name}" src="{img}"
                     style="height:21px; width:21px;" height="21" width="21">
              </a>
            </td>"""
        for url, img, name in _SOCIAL_ICONS
    )

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1,
        minimum-scale=1, maximum-scale=1">
  <meta http-equiv="X-UA-Compatible" content="IE=Edge">
  <style type="text/css">
    body, p, div {{ font-family: arial, helvetica, sans-serif; font-size: 14px; }}
    body {{ color: #000000; }}
    body a {{ color: #1188E6; text-decoration: none; }}
    p {{ margin: 0; padding: 0; }}
    table.wrapper {{ width: 100% !important; table-layout: fixed;
                     -webkit-font-smoothing: antialiased; }}
    img.max-width {{ max-width: 100% !important; }}
    ul.ci-list {{ margin: 8px 0 8px 0; padding-left: 20px; }}
    ul.ci-list li {{ margin-bottom: 6px; line-height: 22px; }}
  </style>
</head>
<body>
  <center class="wrapper" data-link-color="#1188E6"
          data-body-style="font-size:14px; font-family:arial,helvetica,sans-serif;
                           color:#000000; background-color:#FFFFFF;">
    <div class="webkit">
      <table cellpadding="0" cellspacing="0" border="0" width="100%"
             class="wrapper" bgcolor="#FFFFFF">
        <tr>
          <td valign="top" bgcolor="#FFFFFF" width="100%">
            <table width="100%" role="content-container" align="center"
                   cellpadding="0" cellspacing="0" border="0">
              <tr><td width="100%">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                  <tr><td>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0"
                           style="width:100%; max-width:600px;" align="center">
                      <tr>
                        <td style="padding:0px 0px 0px 0px; color:#000000;
                                   text-align:left;" bgcolor="#FFFFFF" width="100%" align="left">

                          <!-- Banner image -->
                          <table class="wrapper" role="module" border="0"
                                 cellpadding="0" cellspacing="0" width="100%"
                                 style="table-layout:fixed;">
                            <tbody><tr>
                              <td style="font-size:6px; line-height:10px;
                                         padding:0px 0px 0px 0px;"
                                  valign="top" align="center">
                                <img class="max-width" border="0"
                                     style="display:block; color:#000000;
                                            text-decoration:none;
                                            font-family:Helvetica,arial,sans-serif;
                                            font-size:16px; max-width:100% !important;
                                            width:100%; height:auto !important;"
                                     width="600"
                                     alt="Maximizer Competitive Intelligence"
                                     src="{BANNER_URL}">
                              </td>
                            </tr></tbody>
                          </table>

                          {body_html}

                          <!-- Sign-off -->
                          <table role="module" border="0" cellpadding="0"
                                 cellspacing="0" width="100%" style="table-layout:fixed;">
                            <tbody><tr>
                              <td style="padding:24px 16px 24px 16px; line-height:22px;
                                         text-align:inherit;" height="100%" valign="top">
                                <div style="font-family:inherit; text-align:inherit;">
                                  This report is for internal use only.<br>
                                  <strong>The Maximizer Team</strong>
                                </div>
                              </td>
                            </tr></tbody>
                          </table>

                          <!-- Divider -->
                          <table role="module" border="0" cellpadding="0"
                                 cellspacing="0" width="100%" style="table-layout:fixed;">
                            <tbody><tr>
                              <td style="padding:0px 0px 0px 0px;"
                                  height="100%" valign="top">
                                <table border="0" cellpadding="0" cellspacing="0"
                                       align="center" width="100%" height="1px"
                                       style="line-height:1px; font-size:1px;">
                                  <tbody><tr>
                                    <td style="padding:0px 0px 1px 0px;"
                                        bgcolor="#E0E5E5"></td>
                                  </tr></tbody>
                                </table>
                              </td>
                            </tr></tbody>
                          </table>

                          <!-- Social icons -->
                          <table role="module" border="0" cellpadding="0"
                                 cellspacing="0" width="100%" style="table-layout:fixed;">
                            <tbody><tr>
                              <td valign="top"
                                  style="padding:12px 0px 0px 0px; font-size:10px;
                                         line-height:6px;" align="center">
                                <table align="center">
                                  <tbody><tr>{social_tds}</tr></tbody>
                                </table>
                              </td>
                            </tr></tbody>
                          </table>

                          <!-- Maximizer logo -->
                          <table class="wrapper" role="module" border="0"
                                 cellpadding="0" cellspacing="0" width="100%"
                                 style="table-layout:fixed;">
                            <tbody><tr>
                              <td style="font-size:6px; line-height:10px;
                                         padding:18px 0px 0px 0px;"
                                  valign="top" align="center">
                                <img class="max-width" border="0"
                                     style="display:block; color:#000000;
                                            text-decoration:none;
                                            font-family:Helvetica,arial,sans-serif;
                                            font-size:16px; max-width:25% !important;
                                            width:25%; height:auto !important;"
                                     width="150" alt="Maximizer" src="{_MAXIMIZER_LOGO}">
                              </td>
                            </tr></tbody>
                          </table>

                          <!-- Address -->
                          <table role="module" border="0" cellpadding="0"
                                 cellspacing="0" width="100%" style="table-layout:fixed;">
                            <tbody><tr>
                              <td style="padding:8px 0px 8px 0px; line-height:22px;
                                         text-align:inherit;" height="100%" valign="top">
                                <div style="font-family:inherit; text-align:center;">
                                  <span style="font-weight:bold; font-size:14px;
                                               color:#343738;">Maximizer Services Inc.</span>
                                </div>
                                <div style="font-family:inherit; text-align:center;">
                                  <span style="font-size:12px; color:#343738;">
                                    Unit 260-60 Smithe St, Vancouver, BC</span>
                                </div>
                                <div style="font-family:inherit; text-align:center;">
                                  <span style="font-size:12px; color:#343738;">
                                    V6B 0P5 Canada</span>
                                </div>
                              </td>
                            </tr></tbody>
                          </table>

                        </td>
                      </tr>
                    </table>
                  </td></tr>
                </table>
              </td></tr>
            </table>
          </td>
        </tr>
      </table>
    </div>
  </center>
</body>
</html>"""


# ── Section assembly ──────────────────────────────────────────────────────────

def _build_body(sections: dict, month_name: str) -> str:
    """Assemble all content sections into template-matching table modules."""
    out = ""

    # H1 title
    out += _h1_module(f"Competitive Intelligence — {month_name}")

    section_map = [
        ("INTRODUCTION",     "Introduction",         _render_introduction),
        ("COMPETITIVE NEWS", "Competitive News",     _render_news_stories),
        ("PRODUCT UPDATES",  "Product Updates",      _render_product_updates),
    ]

    for key, title, renderer in section_map:
        if key in sections and sections[key].strip():
            out += _h2_module(title)
            out += _text_module(renderer(sections[key]))

    return out


# ── Table module templates ────────────────────────────────────────────────────

def _h1_module(title: str) -> str:
    return f"""
    <table role="module" border="0" cellpadding="0" cellspacing="0" width="100%"
           style="table-layout:fixed;">
      <tbody><tr>
        <td style="padding:18px 16px 0px 16px; line-height:40px; text-align:inherit;"
            height="100%" valign="top">
          <h1 style="font-family:inherit; font-size:24px; margin:0;">
            {_escape(title)}
          </h1>
        </td>
      </tr></tbody>
    </table>"""


def _h2_module(title: str) -> str:
    return f"""
    <table role="module" border="0" cellpadding="0" cellspacing="0" width="100%"
           style="table-layout:fixed;">
      <tbody><tr>
        <td style="padding:18px 16px 4px 16px; line-height:30px; text-align:inherit;"
            height="100%" valign="top">
          <h2 style="font-family:inherit; font-size:18px; margin:0;">
            {_escape(title)}
          </h2>
        </td>
      </tr></tbody>
    </table>"""


def _text_module(inner_html: str) -> str:
    return f"""
    <table role="module" border="0" cellpadding="0" cellspacing="0" width="100%"
           style="table-layout:fixed;">
      <tbody><tr>
        <td style="padding:0px 16px 8px 16px; line-height:22px; text-align:inherit;"
            height="100%" valign="top">
          <div style="font-family:inherit; text-align:inherit;">{inner_html}</div>
        </td>
      </tr></tbody>
    </table>"""


# ── Section parsers ───────────────────────────────────────────────────────────

def _parse_sections(text: str) -> dict:
    """Split plain-text newsletter into named sections."""
    section_names = ["INTRODUCTION", "COMPETITIVE NEWS", "PRODUCT UPDATES"]
    pattern = "(" + "|".join(re.escape(s) for s in section_names) + ")"
    parts = re.split(pattern, text)

    sections: dict[str, str] = {}
    current = None
    for part in parts:
        if part in section_names:
            current = part
            sections[current] = ""
        elif current:
            sections[current] = part.strip()

    return sections


# ── Markdown / artefact stripping ─────────────────────────────────────────────

def _preprocess(text: str) -> str:
    """
    Strip all Markdown artefacts from a section before rendering.
    Order matters: bold/italic before lone-asterisk cleanup.
    """
    # 1. Horizontal rules
    text = re.sub(r"^\s*---+\s*$", "", text, flags=re.MULTILINE)
    # 2. Bold **text** → text
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    # 3. Italic *text* → text
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
    # 4. Leading asterisk bullets "* item" → "- item"  (safe after bold/italic stripped)
    text = re.sub(r"^[ \t]*\*[ \t]+", "- ", text, flags=re.MULTILINE)
    # 5. Any remaining stray asterisks
    text = re.sub(r"\*+", "", text)
    return text.strip()


def _escape(text: str) -> str:
    """HTML-escape a string."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _safe(text: str) -> str:
    """Preprocess then HTML-escape."""
    return _escape(_preprocess(text))


# ── Section renderers ─────────────────────────────────────────────────────────

def _render_introduction(text: str) -> str:
    """
    Render Introduction: prose paragraphs followed by a bullet list of takeaways.
    """
    text = _preprocess(text)
    lines = text.splitlines()

    prose_lines: list[str] = []
    bullet_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("-", "•")):
            bullet_lines.append(re.sub(r"^[-•]\s*", "", stripped))
        else:
            prose_lines.append(stripped)

    out = ""
    if prose_lines:
        out += "<br>".join(_escape(l) for l in prose_lines)
    if bullet_lines:
        items = "".join(f"<li>{_escape(l)}</li>" for l in bullet_lines)
        out += f'<ul class="ci-list">{items}</ul>'
    return out


def _render_news_stories(text: str) -> str:
    """
    Render Competitive News stories. Each story has a headline followed by
    'What happened:', 'Why it matters:', and 'How we should respond:' labels.
    """
    text = _preprocess(text)
    if not text.strip():
        return "<em>No significant competitive news this period.</em>"

    # Split into individual stories on blank lines
    raw_stories = re.split(r"\n{2,}", text.strip())
    stories_html: list[str] = []

    for story_block in raw_stories:
        if not story_block.strip():
            continue
        lines = [l.strip() for l in story_block.splitlines() if l.strip()]
        if not lines:
            continue

        story_out = ""
        # First non-label line is the headline
        headline_done = False
        for line in lines:
            label_match = re.match(
                r"^(What happened|Why it matters|How we should respond)\s*:(.*)$",
                line, re.IGNORECASE
            )
            if label_match:
                label = label_match.group(1).strip()
                body = label_match.group(2).strip()
                story_out += f"<br><strong>{_escape(label)}:</strong> {_escape(body)}"
            else:
                if not headline_done:
                    story_out += f"<strong>{_escape(line)}</strong>"
                    headline_done = True
                else:
                    story_out += f"<br>{_escape(line)}"

        if story_out:
            stories_html.append(story_out)

    return "<br><br>".join(stories_html) if stories_html else \
        "<em>No significant competitive news this period.</em>"


def _render_product_updates(text: str) -> str:
    """
    Render Product Updates as a bullet list.
    Non-bullet lines (e.g. a 'Maximizer updates' subheading) are rendered as bold.
    """
    text = _preprocess(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return "<em>No product updates this period.</em>"

    bullet_items: list[str] = []
    non_bullets: list[str] = []
    out_parts: list[str] = []

    def _flush_bullets() -> None:
        if bullet_items:
            items = "".join(f"<li>{_escape(l)}</li>" for l in bullet_items)
            out_parts.append(f'<ul class="ci-list">{items}</ul>')
            bullet_items.clear()

    for line in lines:
        if line.startswith(("-", "•")):
            content = re.sub(r"^[-•]\s*", "", line)
            bullet_items.append(content)
        else:
            _flush_bullets()
            out_parts.append(f"<strong>{_escape(line)}</strong>")

    _flush_bullets()
    return "".join(out_parts)


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
        INTRODUCTION
        No significant competitive changes were detected this month.
        All monitored competitor pages remained stable.
    """).strip()
