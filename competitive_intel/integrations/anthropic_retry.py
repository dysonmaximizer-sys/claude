"""
Retry policy for transient Anthropic API failures.

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
