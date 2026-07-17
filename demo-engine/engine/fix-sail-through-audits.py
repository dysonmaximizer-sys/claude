#!/usr/bin/env python3
"""
One-time patch for the 2026-07-17 Sail Through Audits seed.

Why: the seeder set Date Last Contacted to 9 days ago, but the newest
interaction it created is ~11 months old (the yearly cadence tops out a
year back). A record that claims contact 9 days ago with nothing on the
timeline to show for it will bother exactly the kind of viewer this tour
is built for. This adds ONE incoming call 9 days ago that matches the
story (Céline turns 65 this year; her OAS question), and appends it to
the existing manifest so cleanup still removes everything.

Run:  cd "/Users/lewisdyson/Claude Code/demo-engine" && set -a && source .env && set +a && python3 engine/fix-sail-through-audits.py

Safe to run once. Refuses to run twice (checks the manifest for its label).
Fold this into the seeder (a years_ago=0 call row) before the next fresh seed.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests --break-system-packages")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifests",
                        "sail-through-audits-manifest.json")
LABEL = "Céline - OAS application question (recent)"
TODAY = datetime.now()


def d(days_offset: int, hm: str) -> str:
    from zoneinfo import ZoneInfo
    day = TODAY + timedelta(days=days_offset)
    local = day.replace(hour=int(hm[:2]), minute=int(hm[3:5]), second=0, microsecond=0,
                        tzinfo=ZoneInfo("America/Vancouver"))
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def main() -> None:
    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only).")
    if not os.path.exists(MANIFEST):
        sys.exit("No sail-through-audits manifest - seed the story first.")
    with open(MANIFEST) as f:
        manifest = json.load(f)
    if any(r.get("label") == LABEL for r in manifest.get("records", [])):
        sys.exit("Patch already applied (call is in the manifest). Nothing to do.")

    hh = next((r["key"] for r in manifest["records"]
               if r["kind"] == "AbEntry" and "Household" in r["label"]), None)
    if not hh:
        sys.exit("Household key not found in manifest - paste this to Claude.")

    time.sleep(0.35)
    r = requests.post(f"{BASE}/Create",
                      headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                      json={"InteractionLog": {"Data": {
                          "Key": None,
                          "Subject": "Céline - OAS application question",
                          "Description": "Céline called ahead of turning 65: OAS application timing and "
                                         "whether to defer. Booked it as an agenda item for the fall review.",
                          "Type": "60001",
                          "StartDate": d(-9, "11:00"), "EndDate": d(-9, "11:14"),
                          "User": "$CURRENTUSER()", "AbEntryKey": hh, "Direction": 1,
                      }}, "Compatibility": {"AbEntryKey": "2.0"}},
                      timeout=30)
    data = r.json()
    key = data.get("InteractionLog", {}).get("Data", {}).get("Key")
    if not key:
        sys.exit(f"Create failed - paste this to Claude: {json.dumps(data)[:400]}")

    manifest["records"].append({"kind": "InteractionLog", "key": key, "label": LABEL})
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print("Done: recent call added 9 days back (matches Date Last Contacted).")
    print("Manifest updated - cleanup still removes everything.")


if __name__ == "__main__":
    main()
