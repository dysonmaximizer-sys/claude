#!/usr/bin/env python3
"""
Webinar McGill Catch — enrich source records so IQ Boost answers cite them.

Principle (Lewis, 2026-08-17): steer demo AI output by enriching the REAL
records it reads, never by hiding instructions in the data. Everything on
the record may appear on screen.

What this does:
1. June cottage call: rewrites the Description to contain the exact
   quotable line the demo wants cited:
   "Priya raised possibly selling the cottage; wants to understand
   capital gains before deciding."
   Tries InteractionLog Update first (unvalidated on this tenant); if the
   read-back doesn't show the new text, falls back to delete + recreate
   with identical dates/fields (create IS validated), and swaps the key
   in the manifest.
2. Prints the three-question test protocol. IQ Boost has no API surface,
   so testing is manual in the UI; iterate the source notes, not prompts.

The Focal summary note itself is handled by add-focal-summary-note.py
(its text already carries the anchors: $780,000 estimate, 1999 purchase,
"possible listing in spring", RESP contribution "before end of September").

Run:  cd "$HOME/Claude Code/demo-engine"
      set -a; source .env; set +a
      python3 engine/enrich-webinar-story.py
"""
import json, os, sys, time
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import requests

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "manifests", "webinar-mcgill-catch-manifest.json")

HH = "Q29tcGFueQkyNjA4MTQyNTIxMTgzNTEwNzAwMjNDCTA="  # Halloran Family household
MASTER = "VXNlcglNQVNURVI="  # rule 10 owner, displays "Barb Smith"

NEW_DESC = ("Priya raised possibly selling the cottage; wants to understand "
            "capital gains before deciding. Timing and what to do with the "
            "proceeds to be discussed at an upcoming review. No decision yet.")
SUBJECT = "Call from Priya - thinking about selling the cottage"


def call(endpoint: str, payload: dict) -> dict:
    time.sleep(0.4)
    r = requests.post(f"{BASE}/{endpoint}",
                      headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                      json=payload, timeout=30)
    if r.status_code == 429:
        time.sleep(float(r.headers.get("Retry-After", "2")))
        r = requests.post(f"{BASE}/{endpoint}",
                          headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                          json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def read_log(key: str) -> Optional[dict]:
    data = call("Read", {"InteractionLog": {
        "Scope": {"Fields": {"Key": 1, "Subject": 1, "Description": 1, "Type": 1,
                             "StartDate": 1, "EndDate": 1, "Direction": 1}},
        "Criteria": {"SearchQuery": {"Key": {"$EQ": key}}},
    }, "Compatibility": {"AbEntryKey": "2.0"}})
    rows = data.get("InteractionLog", {}).get("Data", []) or []
    return rows[0] if rows else None


def main():
    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (source .env - demo tenant only).")
    with open(MANIFEST) as f:
        manifest = json.load(f)
    entry = next((r for r in manifest["records"]
                  if r["kind"] == "InteractionLog" and "cottage call" in r["label"]), None)
    if not entry:
        sys.exit("June cottage call not found in manifest - stopping.")
    key = entry["key"]

    before = read_log(key)
    if not before:
        sys.exit("Could not read the June call back - stopping before any write.")
    if "capital gains" in str(before.get("Description", "")):
        print("June call already carries the quotable line - nothing to do.")
        return

    print("Attempting InteractionLog Update ...")
    call("Update", {"InteractionLog": {"Data": {"Key": key, "Description": NEW_DESC}},
                    "Compatibility": {"AbEntryKey": "2.0"}})
    after = read_log(key)
    if after and "capital gains" in str(after.get("Description", "")):
        print("Update verified by read-back. Done.")
    else:
        print("Update did not stick (expected possibility - unvalidated op). Recreating ...")
        old = before
        data = call("Create", {"InteractionLog": {"Data": {
            "Key": None, "Subject": SUBJECT, "Description": NEW_DESC,
            "Type": old.get("Type"), "StartDate": old.get("StartDate"),
            "EndDate": old.get("EndDate"), "User": MASTER,
            "AbEntryKey": HH, "Direction": old.get("Direction", 1),
        }}, "Compatibility": {"AbEntryKey": "2.0"}})
        new_key = data.get("InteractionLog", {}).get("Data", {}).get("Key")
        if not new_key:
            sys.exit("Recreate FAILED - old record left untouched. Paste this output back.")
        check = read_log(new_key)
        if not check or "capital gains" not in str(check.get("Description", "")):
            sys.exit("Recreated record failed read-back - old record left in place. Investigate.")
        call("Delete", {"InteractionLog": {"Data": {"Key": key}}})
        entry["key"] = new_key
        entry["label"] = "Priya cottage call (June feel, enriched)"
        with open(MANIFEST, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"Recreated with enriched description, old record deleted, manifest updated.")
        print(f"read-back StartDate={check.get('StartDate')} (should match {old.get('StartDate')})")

    print("""
MANUAL TEST PROTOCOL (IQ Boost has no API; test in the UI on the Halloran household):
  Q1. What should I follow up on from today's meeting?
      Expect: McGill/Maya line connected to the open RESP task and allocation note.
  Q2. Where do the Hallorans stand on selling the cottage?
      Expect: today's Focal summary (780K / 1999 / possible spring listing /
      capital gains question) PLUS the June call with the quotable line.
  Q3. What did we agree on RESP contributions?
      Expect: contribution to be processed before end of September (from the
      Focal summary's action item).
  If an answer is weak: enrich the note it should draw from and retest.
  Never add instruction-style text to any record; everything can appear on screen.""")


if __name__ == "__main__":
    main()
