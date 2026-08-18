"""
Standalone Anthropic API key check — run this locally with the same key the
GitHub Actions workflow uses to find out whether the KEY is funded.

Run from the competitive_intel/ directory:
    python3 -m scripts.check_api_key
    python3 -m scripts.check_api_key --model claude-sonnet-4-6
    python3 -m scripts.check_api_key --key sk-ant-...      # test another key

It makes two calls:
  1. GET  /v1/models   — unbilled. Does the key authenticate at all?
  2. POST /v1/messages — billed, 1 token, cheapest model. Can it pay?

Stage 1 passing while stage 2 fails means the key is valid and live but its
workspace/org cannot pay — i.e. the credits were topped up somewhere else, or
the workspace has a $0 spend limit. That is the distinction to quote to
whoever manages the Anthropic console, along with the request id and org id
printed below.

Exit code: 0 if the key can run billed inference, 1 otherwise.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

sys.path.insert(0, str(Path(__file__).parent.parent))
from integrations.anthropic_preflight import check_api_key, diagnosis  # noqa: E402


def _fingerprint(key: str) -> str:
    """Identify a key without printing it: prefix, length, last 4 chars."""
    if not key:
        return "(not set)"
    if len(key) <= 16:
        return f"{key[:4]}… (len {len(key)})"
    return f"{key[:11]}…{key[-4:]} (len {len(key)})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether an Anthropic API key is funded.")
    parser.add_argument("--model", default=None, help="Model to test (default: config.PREFLIGHT_MODEL)")
    parser.add_argument("--key", default=None, help="Key to test (default: ANTHROPIC_API_KEY from env/.env)")
    parser.add_argument("--json", action="store_true", help="Print the raw result dict as JSON")
    args = parser.parse_args()

    key = args.key or os.environ.get("ANTHROPIC_API_KEY", "")
    result = check_api_key(api_key=key, model=args.model)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    print()
    print("Anthropic API key check")
    print("=" * 72)
    print(f"  Key         : {_fingerprint(key)}")
    print(f"  Source      : {'--key argument' if args.key else 'ANTHROPIC_API_KEY (env / .env)'}")
    print(f"  Model tested: {result['model']}")
    print(f"  Org id      : {result['organization_id'] or '(unknown)'}")
    print(f"  Request id  : {result['request_id'] or '(none)'}")
    print("-" * 72)

    if result["ok"]:
        print("  RESULT: PASS")
        print("  Stage 1 (GET /v1/models)   : authenticated")
        print("  Stage 2 (POST /v1/messages): billed inference succeeded")
        print()
        print(f"  {diagnosis(result)}")
        print()
        return 0

    stage_labels = {
        "key": "no key supplied",
        "auth": "stage 1 — GET /v1/models (unbilled auth check)",
        "inference": "stage 2 — POST /v1/messages (billed inference check)",
    }
    print("  RESULT: FAIL")
    print(f"  Failed at   : {stage_labels.get(result['stage'], result['stage'])}")
    if result["stage"] == "inference":
        print("  Stage 1 (GET /v1/models)   : PASSED — key authenticates, not revoked")
    print(f"  HTTP status : {result['status']}")
    print(f"  Error type  : {result['error_type']}")
    print(f"  Message     : {result['message']}")
    print()
    print("  Diagnosis:")
    for line in _wrap(diagnosis(result), 68):
        print(f"    {line}")
    print()
    print("  Verbatim response body (quote this, with the request id above):")
    print("  " + "-" * 70)
    for line in (result["body"] or "(empty)").splitlines() or ["(empty)"]:
        print(f"  {line}")
    print("  " + "-" * 70)
    print()
    return 1


def _wrap(text: str, width: int) -> list:
    import textwrap
    return textwrap.wrap(text, width=width) or [""]


if __name__ == "__main__":
    sys.exit(main())
