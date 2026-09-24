"""
Awareness agent — decides whether an alert-worthy insight is news Maximizer is
already a party to, so it can be kept out of Teams.

Feedback (2026-09-24): intel where Maximizer is itself a participant — a joint
webinar, a partner shipping a Maximizer integration, a co-announcement — is
logged correctly but adds nothing in the Teams chat, because we already know.

Why this is not a keyword filter: a change that names Maximizer is just as
often the MOST urgent intel we can get — a "Maximizer vs X" comparison page, a
"switch from Maximizer" offer, a migration tool, a partner dropping or gating
its Maximizer integration. Those are exactly what the scoring rubric ranks
highest ("a direct attack on Maximizer's positioning"). So the keyword is only
a gate; the model decides PARTY (suppress) versus everything else (alert).

Design rules:
  • Separate from scoring. The significance score is untouched, and the scoring
    prompt is not modified, so this cannot shift scores.
  • Keyword gate first. Only insights whose URL or diff mentions Maximizer reach
    the model, so almost every insight costs nothing extra.
  • Fail open. Any error, malformed response, or uncertainty returns "alert".
    A duplicate card is a mild annoyance; a suppressed attack is the failure
    that matters.
  • Suppression is Teams-only. The rows stay Scored, keep their summary, and
    still feed the monthly newsletter.
"""

import json
import logging
import re

import anthropic

from integrations.anthropic_retry import response_text, retry_transient
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_MAXIMIZER = re.compile(r"maximizer", re.IGNORECASE)


@retry_transient
def _create(**kwargs):
    """messages.create with backoff on 429/5xx/connection errors."""
    return client.messages.create(**kwargs)


SYSTEM_PROMPT = """You review competitive intelligence for Maximizer, a CRM for \
wealth management and insurance advisors, before it is posted to the sales team's \
chat. Each item is a change detected on a competitor's or partner's website that \
mentions Maximizer.

Classify the item as exactly one of:

PARTY — the news is a joint activity that Maximizer is part of, so Maximizer \
already knows about it. Examples: an integration WITH Maximizer launched, promoted \
or updated, a joint webinar or event, a co-marketing campaign or co-announcement, \
Maximizer listed as a partner, a Maximizer customer story on a partner's site. \
This holds even when only the other company announces it: treat an integration \
that connects to Maximizer as a Maximizer partnership, and do not require evidence \
that Maximizer co-announced it.

ALERT — anything else. In particular:
- Maximizer named as a competitor, compared against, or criticised
- Offers to switch or migrate away from Maximizer, or migration tools
- An integration with Maximizer removed, deprecated, paywalled, or degraded
- Claims about Maximizer's product, pricing, customers, or roadmap
- The change contains other significant news beyond the Maximizer joint activity \
(for example, it also announces integrations with other CRMs, a new product, or a \
pricing change). The other news is still worth an alert.
- Maximizer is mentioned only incidentally and the real news is something else

When unsure, choose ALERT.

Respond ONLY with a JSON object. No prose, no markdown.
Format: {"label": "PARTY" | "ALERT", "reason": "<one short sentence>"}"""


def _excerpt(text: str, head: int = 600, window: int = 700, cap: int = 3000) -> str:
    """
    The diff's opening lines plus a window around every Maximizer mention.

    Not simply the first N characters: on LinkedIn and similar pages the
    Maximizer post sits below follower counts and employee lists, so a head-only
    slice shows the model the noise and hides the news (seen on real Continuum
    rows, 2026-09-24).
    """
    text = text or ""
    if len(text) <= cap:
        return text
    spans = [(0, head)]
    for m in _MAXIMIZER.finditer(text):
        spans.append((max(0, m.start() - window), min(len(text), m.end() + window)))
    spans.sort()
    merged = [list(spans[0])]
    for lo, hi in spans[1:]:
        if lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return "\n[...]\n".join(text[lo:hi] for lo, hi in merged)[:cap]


def mentions_maximizer(item: dict) -> bool:
    """Deterministic gate: does the row's URL or diff name Maximizer at all?"""
    return bool(_MAXIMIZER.search(item.get("url") or "")
                or _MAXIMIZER.search(item.get("raw_change") or ""))


def classify_insight(competitor_name: str, items: list[dict]) -> tuple[bool, str]:
    """
    Decide whether one insight (a cluster of rows) is Maximizer-party news.

    `items` are the cluster's rows, each with `url`, `raw_change`, and
    `summary` (the scoring reasoning at this point in the poll).

    Returns (suppress, reason). suppress is True only when the model clearly
    says PARTY; every other outcome, including errors, returns False.
    """
    relevant = [it for it in items if mentions_maximizer(it)]
    if not relevant:
        return False, ""

    lines = []
    for i, it in enumerate(items):
        lines.append(
            f"[{i}] url={it.get('url', '')}\n"
            f"    scoring note: {(it.get('summary') or '').strip()[:400]}\n"
            f"    detected change:\n{_excerpt((it.get('raw_change') or '').strip())}"
        )
    user_content = (
        f"Source: {competitor_name}\n"
        f"{len(items)} page(s) describing one insight:\n\n"
        + "\n\n".join(lines)
        + "\n\nClassify this insight."
    )

    try:
        message = _create(
            model=CLAUDE_MODEL,
            max_tokens=150,
            thinking={"type": "disabled"},
            system=[{"type": "text", "text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": user_content}],
        )
        result = json.loads(response_text(message).strip())
        label = str(result.get("label", "")).strip().upper()
        reason = str(result.get("reason", "")).strip()
    except (json.JSONDecodeError, AttributeError, ValueError, TypeError) as e:
        logger.error("Awareness check unparseable for %s (alerting): %s", competitor_name, e)
        return False, ""
    except Exception as e:  # API errors included: never let this block an alert
        logger.error("Awareness check failed for %s (alerting): %s", competitor_name, e)
        return False, ""

    logger.info("  → Awareness check for %s: %s — %s", competitor_name, label or "?", reason)
    return label == "PARTY", reason
