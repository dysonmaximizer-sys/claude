"""
Anthropic API preflight — proves the key can actually run billed inference
BEFORE a job fetches anything or writes a single row to Notion.

Why this exists: on 2026-08-04 scoring started failing mid-run with
`400 invalid_request_error: credit balance too low`. The daily poll kept
logging changes to Notion and only then discovered it could not score them,
which stranded 183 rows as permanently-"Unscored" (the dedupe treated them as
already-logged duplicates on every later run). Failing fast leaves the
database untouched.

The check runs in two stages so the failure is diagnosable, not just fatal:

  1. GET  /v1/models   — unbilled. Proves the key exists, is not revoked, and
     is authenticated. Also returns the `anthropic-organization-id` header.
  2. POST /v1/messages — billed (1 token). Proves the key's WORKSPACE/org can
     actually pay for inference.

Stage 1 passing while stage 2 fails is the signature of a billing-scope
problem, not a bad key: an Anthropic key belongs to one workspace inside one
org, so credits topped up on a different org or a $0 workspace spend limit
produce exactly this split.

Uses `requests` rather than the anthropic SDK so response headers (request id,
org id) and the raw error body are available verbatim for support tickets.
"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_BASE = "https://api.anthropic.com/v1"
_API_VERSION = "2023-06-01"


def _headers(api_key: str) -> dict:
    return {
        "x-api-key": api_key,
        "anthropic-version": _API_VERSION,
        "content-type": "application/json",
    }


def check_api_key(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 20,
) -> dict:
    """
    Verify the Anthropic API key can run billed inference.

    Returns a result dict — it never raises for an API-level failure:
      {
        "ok": bool,
        "stage": "key" | "auth" | "inference",   # where it got to / failed
        "status": int | None,                    # HTTP status of the failing call
        "error_type": str,                       # e.g. invalid_request_error
        "message": str,                          # verbatim Anthropic message
        "request_id": str,
        "organization_id": str,
        "model": str,
        "body": str,                             # raw response body (truncated)
      }
    """
    from config import PREFLIGHT_MODEL

    api_key = api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY", "")
    model = model or PREFLIGHT_MODEL

    result = {
        "ok": False,
        "stage": "key",
        "status": None,
        "error_type": "",
        "message": "",
        "request_id": "",
        "organization_id": "",
        "model": model,
        "body": "",
    }

    if not api_key:
        result["message"] = "ANTHROPIC_API_KEY is not set in the environment."
        return result

    # ── Stage 1: unbilled auth check ──────────────────────────────────────────
    result["stage"] = "auth"
    try:
        r = requests.get(f"{_BASE}/models?limit=1", headers=_headers(api_key), timeout=timeout)
    except requests.RequestException as e:
        result["message"] = f"Could not reach api.anthropic.com: {e}"
        return result

    result["request_id"] = r.headers.get("request-id", "")
    result["organization_id"] = r.headers.get("anthropic-organization-id", "")
    if r.status_code >= 400:
        result["status"] = r.status_code
        result["body"] = (r.text or "")[:1500]
        result["error_type"], result["message"] = _parse_error(r)
        return result

    # ── Stage 2: billed inference check (1 token) ─────────────────────────────
    result["stage"] = "inference"
    try:
        r = requests.post(
            f"{_BASE}/messages",
            headers=_headers(api_key),
            json={
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            },
            timeout=timeout,
        )
    except requests.RequestException as e:
        result["message"] = f"Could not reach api.anthropic.com: {e}"
        return result

    result["request_id"] = r.headers.get("request-id", result["request_id"])
    result["organization_id"] = (
        r.headers.get("anthropic-organization-id", "") or result["organization_id"]
    )
    result["status"] = r.status_code
    if r.status_code >= 400:
        result["body"] = (r.text or "")[:1500]
        result["error_type"], result["message"] = _parse_error(r)
        return result

    result["ok"] = True
    return result


def _parse_error(r: requests.Response) -> tuple:
    """Pull (error_type, message) out of an Anthropic error body."""
    try:
        err = r.json().get("error", {})
        return err.get("type", ""), err.get("message", "")
    except ValueError:
        return "", (r.text or "")[:500]


def diagnosis(result: dict) -> str:
    """A human-readable read on what a failed check_api_key() result means."""
    if result["ok"]:
        return "Key is authenticated and can run billed inference."

    if result["stage"] == "key":
        return "No key was supplied — set ANTHROPIC_API_KEY."

    if result["stage"] == "auth":
        return (
            "The key failed the unbilled auth check, so this is the key itself: "
            "wrong value, revoked, or disabled. Re-issue it in the Anthropic "
            "console and update the ANTHROPIC_API_KEY secret."
        )

    # stage == "inference": auth passed, billed call failed.
    if "credit balance" in (result["message"] or "").lower():
        return (
            "Auth passed but billed inference was refused for insufficient "
            "credit. The key is valid and live, so this is a BILLING SCOPE "
            "problem, not a bad key. An Anthropic key belongs to exactly one "
            "workspace inside one org, and credit/spend limits apply per "
            "workspace. Check, in this order: (1) that the org id below is the "
            "org that was topped up; (2) that the workspace this key belongs "
            "to has a non-zero spend limit; (3) that the credits were not "
            "added to a different org or workspace."
        )
    return (
        "Auth passed but the billed test call failed. See the verbatim error "
        "and request id below."
    )


def preflight_or_exit(job_name: str = "job", fatal: bool = True) -> dict:
    """
    Run the preflight and terminate the process non-zero if it fails.

    Call this FIRST in any job that scores — before fetching changes and before
    writing anything to Notion.

    fatal=False downgrades a failure to a warning and returns instead of
    exiting. Used by --dry-run paths, which make no billed calls and so stay
    useful (inspecting the backlog, checking competitor matching) even while the
    key is unfunded.
    """
    import sys

    result = check_api_key()
    if result["ok"]:
        logger.info(
            "Preflight OK — Anthropic key can run billed inference (model %s, org %s)",
            result["model"], result["organization_id"] or "unknown",
        )
        return result

    logger.error(
        "PREFLIGHT FAILED at the %s stage — aborting %s before any fetch or write.",
        result["stage"], job_name,
    )
    logger.error("  HTTP status : %s", result["status"])
    logger.error("  Error type  : %s", result["error_type"])
    logger.error("  Message     : %s", result["message"])
    logger.error("  Request id  : %s", result["request_id"] or "(none)")
    logger.error("  Org id      : %s", result["organization_id"] or "(unknown)")
    logger.error("  Model tried : %s", result["model"])
    logger.error("  Diagnosis   : %s", diagnosis(result))
    logger.error(
        "  Nothing was fetched and nothing was written to Notion. Run "
        "`python3 -m scripts.check_api_key` locally for the full detail."
    )
    if not fatal:
        logger.warning(
            "Continuing anyway: this is a dry run, which makes no billed calls. "
            "A live run would have stopped here."
        )
        return result
    sys.exit(1)
