"""
Shared plumbing for Anthropic calls: retry policy and response parsing.

Why: on 2026-08-28 a single HTTP 500 (`api_error: Unable to complete this
request`) on one row out of 27 failed the whole daily poll. That produced a red
run, a "daily poll FAILED" Teams card, and then a "PIPELINE PROBLEM" card every
day after, for a blip that lasted one request.

Transient means worth retrying: 429 (rate limited), 5xx (Anthropic-side), and
connection/timeout errors. NOT retried: 400 invalid_request_error — that is the
credit-balance failure, which is a standing condition, and hammering it wastes
time and hides the diagnosis.

The SDK does some retrying of its own; this is a deliberate outer layer with
longer backoff, because the failure mode we care about is a brief outage rather
than a single unlucky packet.
"""

import logging

import anthropic
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4


def is_transient(exc: BaseException) -> bool:
    """True if this exception is worth retrying."""
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError,
                        anthropic.RateLimitError, anthropic.InternalServerError)):
        return True
    # Anything else carrying a 429 or 5xx status, in case the SDK's exception
    # hierarchy shifts between versions.
    status = getattr(exc, "status_code", None)
    return status == 429 or (isinstance(status, int) and 500 <= status < 600)


retry_transient = retry(
    retry=retry_if_exception(is_transient),
    stop=stop_after_attempt(MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,  # surface the original error, not tenacity's RetryError
)


def response_text(message) -> str:
    """
    Return the text of a Messages API response, ignoring non-text blocks.

    Why this exists: on 2026-09-01 the monthly newsletter died with
    `'ThinkingBlock' object has no attribute 'text'`. Every agent read
    `message.content[0].text`, which assumes the first block is text. Sonnet 5
    runs ADAPTIVE thinking by default — Sonnet 4.6 did not — so the model decides
    per request whether to think, and when it does, `content[0]` is a
    ThinkingBlock. Short classification calls usually skip thinking and long
    synthesis calls usually don't, which is why scoring kept working while the
    newsletter broke: the same latent bug, hidden by workload shape.

    Concatenates every text block rather than taking the first, since a response
    can legitimately be split across several.

    Raises ValueError when there is no text at all, or when the response was cut
    off by max_tokens — both produce confusing downstream failures (a JSON parse
    error on a truncated object, or an empty summary written to Notion) that are
    far harder to diagnose than an explicit error here.
    """
    text = "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
    if getattr(message, "stop_reason", None) == "max_tokens":
        raise ValueError(
            f"response hit max_tokens ({len(text)} chars of text recovered) — raise "
            f"max_tokens, or disable thinking on this call so the budget is not "
            f"spent reasoning"
        )
    if not text.strip():
        blocks = [getattr(b, "type", "?") for b in message.content]
        raise ValueError(f"response contained no text block (blocks: {blocks})")
    return text
