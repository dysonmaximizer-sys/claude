"""
Add the two Notion properties the Maximizer-party filter writes to.

Run from the competitive_intel/ directory:
    python3 -m scripts.add_suppression_properties            # report only
    python3 -m scripts.add_suppression_properties --apply    # create them

  • Teams Suppressed   (checkbox)   ticked when an alert-worthy row was kept out
                                    of Teams because Maximizer is a party to it
  • Suppression Reason (rich text)  the awareness agent's one-line reason

Without these, mark_teams_suppressed() is a rejected write. Additive only and
safe to re-run: an existing property is left alone.
"""

import argparse
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.notion_client import _CHANGES_DB, _HEADERS, _BASE  # noqa: E402

WANTED = {
    "Teams Suppressed": {"checkbox": {}},
    "Suppression Reason": {"rich_text": {}},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Add the Teams suppression properties.")
    parser.add_argument("--apply", action="store_true", help="Create the missing properties")
    args = parser.parse_args()

    r = requests.get(f"{_BASE}/databases/{_CHANGES_DB}", headers=_HEADERS, timeout=30)
    if r.status_code >= 400:
        print(f"Could not read the database schema: {r.status_code} {r.text[:400]}")
        return 1
    props = r.json()["properties"]

    missing = {}
    for name, spec in WANTED.items():
        kind = next(iter(spec))
        if name not in props:
            missing[name] = spec
            print(f"  MISSING  {name} ({kind})")
        elif props[name]["type"] != kind:
            print(f"  WRONG TYPE  {name} is {props[name]['type']}, expected {kind}. Fix by hand.")
            return 1
        else:
            print(f"  ok       {name} ({kind})")

    if not missing:
        print("Nothing to do.")
        return 0
    if not args.apply:
        print("Re-run with --apply to create them.")
        return 1

    rp = requests.patch(f"{_BASE}/databases/{_CHANGES_DB}", headers=_HEADERS, timeout=30,
                        json={"properties": missing})
    print(f"PATCH: {rp.status_code}{'' if rp.ok else ' ' + rp.text[:400]}")
    return 0 if rp.ok else 1


if __name__ == "__main__":
    sys.exit(main())
