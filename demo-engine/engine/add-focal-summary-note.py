#!/usr/bin/env python3
"""
Webinar McGill Catch — add the synced Focal AI meeting summary note.

Adds ONE note to the existing Halloran household (webinar-mcgill-catch
story): the Focal-style structured summary of the Aug 19 meeting, dated
the webinar day (Wed 2026-08-19, 10:00 PT). Appends the created key to the
existing manifest so --cleanup in the main seeder removes it too.

Accuracy gates honored (stories/webinar-mcgill-catch.md):
- McGill line buried mid-summary, NOT in action items.
- Action items: cottage valuation contact + RESP contribution only.
- No "grant room" language anywhere.

Run:  cd "$HOME/Claude Code/demo-engine"
      set -a; source .env; set +a
      python3 engine/add-focal-summary-note.py
"""
import json, os, sys, time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import requests

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "manifests", "webinar-mcgill-catch-manifest.json")
HH = "Q29tcGFueQkyNjA4MTQyNTIxMTgzNTEwNzAwMjNDCTA="  # Halloran Family household

def dt_pacific(y, m, day, hm):
    hour, minute = int(hm[:2]), int(hm[3:5])
    local = datetime(y, m, day, hour, minute, tzinfo=ZoneInfo("America/Vancouver"))
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")

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

NOTE_TEXT = """FOCAL AI MEETING SUMMARY (synced from Focal)
Annual Review: Dan & Priya Halloran
Wednesday, August 19, 2026, 10:00 AM PT, 45 minutes, video meeting
Attendees: Dan Halloran, Priya Halloran, Advisor

MEETING SUMMARY

Portfolio review. Walked through year-to-date performance and current allocation. Dan and Priya are comfortable with the mix and no changes were requested. Risk tolerance reconfirmed as unchanged.

Cottage. Dan and Priya are now seriously considering selling the family cottage, most likely listing in spring. Priya estimates its value around $780,000; they purchased it in 1999 for approximately $210,000. Their hesitations are family attachment and timing of the sale. They asked what capital gains would look like on the sale and whether the proceeds could bring Dan's retirement forward by a year or two. They would like to see a projection before making a listing decision.

Family updates. Priya's mother's condo sale closed last month and the family is planning a celebration trip in October. Dan mentioned that Maya got into McGill and starts next September; the family is very proud. Priya has reduced her consulting hours for the fall.

Retirement. Dan reiterated his goal of stepping back from full-time work around 60. Current plan assumptions were reviewed at a high level and will be revisited once the cottage decision is made.

KEY DETAILS

Cottage estimated value: approx. $780,000. Purchased 1999, approx. $210,000. Possible listing: spring.
Risk tolerance: unchanged.
Next annual review: August 2027.

ACTION ITEMS

1. Contact property appraiser to arrange a cottage valuation and gather adjusted cost base documentation. (Advisor)
2. Process this year's RESP contribution before end of September. (Advisor)

FOLLOW-UP

Follow-up email drafted by Focal and sent to Dan and Priya recapping the cottage discussion and confirming next steps."""

def main():
    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (source .env - demo tenant only).")
    if not os.path.exists(MANIFEST):
        sys.exit("Manifest missing - story not seeded; stopping.")
    with open(MANIFEST) as f:
        manifest = json.load(f)
    if any(r.get("label", "").startswith("FOCAL AI MEETING SUMMARY") for r in manifest.get("records", [])):
        sys.exit("Focal summary note already in manifest - not creating a duplicate.")

    when = dt_pacific(2026, 8, 17, "10:45")  # note stamped at meeting end
    data = call("Create", {"Note": {"Data": {
        "Key": None, "ParentKey": HH, "DateTime": when, "Text": NOTE_TEXT,
    }}})
    key = data.get("Note", {}).get("Data", {}).get("Key")
    code = data.get("Code", 0)
    print(f"create Code={code} key={key} datetime_sent={when}")
    if not key:
        sys.exit("Note create failed - nothing written to manifest.")

    manifest["records"].append({"kind": "Note", "key": key, "label": NOTE_TEXT[:50]})
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print("manifest updated")

    # Read-back verification: fetch notes for the household, find ours, print stored DateTime.
    rb = call("Read", {"Note": {
        "Scope": {"Fields": {"Key": 1, "DateTime": 1, "Text": 1}},
        "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": HH}}},
    }})
    for n in rb.get("Note", {}).get("Data", []) or []:
        if n.get("Key") == key:
            print(f"read-back: DateTime={n.get('DateTime')} textstart={str(n.get('Text',''))[:40]!r}")
            break
    else:
        print("read-back: NOTE NOT FOUND - investigate")
    # Audit-note check (rule 5): list any same-day auto notes.
    today = datetime.now().strftime("%Y-%m-%d")
    audits = [n for n in rb.get("Note", {}).get("Data", []) or []
              if str(n.get("DateTime","")).startswith(today)
              and ("Hotlist Task" in str(n.get("Text","")) or "Opportunity created" in str(n.get("Text","")))]
    print(f"audit notes needing sweep: {len(audits)}")

if __name__ == "__main__":
    main()
