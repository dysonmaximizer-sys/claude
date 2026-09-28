#!/usr/bin/env python3
"""Bring the Halloran RESP picture up to date for the Continuum webinar.

Before this, the newest RESP information on the Halloran record was the thin
March note, so IQ Boost's RESP answers (and the "RESP Update" prompt) read as
stale. This adds a recent RESP statement note ~3 weeks before the webinar
and fills the household RESP balance UDF to match.

It deliberately leaves the story's anchors alone: the 2024 allocation note
and the open 2024 task (the McGill catch), the March two-line note ("scroll
back to March"), and Priya's June cottage call. The new note says the
allocation is UNCHANGED, which strengthens the catch rather than resolving it.
Accuracy gate: no "unused grant room" language (Maya is 17; CESG is done).

Usage (repo root):
  set -a; source .env; set +a
  python3 engine/update-webinar-resp.py --demo-day 2026-10-01
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
COMPAT = {"AbEntryKey": "2.0"}
HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "manifests", "webinar-mcgill-catch-manifest.json")
RESP = "Udf/$NAME(WM_KYC etc.\\Balance Sheet\\Liquid\\RESP)"
LABEL = "RESP statement review (webinar refresh)"
BALANCE = 91400  # currency UDF takes a number, not a string (Code -1024 otherwise)

NOTE_TEXT = (
    "RESP statement review (Aug 31 statement). Beneficiary: Maya.\n"
    "Market value: $91,400. Contributions to date: $46,500. "
    "CESG received: $7,200 (lifetime maximum reached).\n"
    "2026 contribution of $2,500 received Aug 28.\n"
    "Allocation unchanged since the 2024 review: approx. 80/20 equities. "
    "No withdrawals to date."
)


def call(endpoint: str, payload: dict) -> dict:
    time.sleep(0.4)  # 429 pacing per CLAUDE.md
    r = requests.post(f"{BASE}/{endpoint}",
                      headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                      json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("Code") == -2:
        sys.exit("API auth failed - the PAT has likely expired: renew it in .env and rerun.")
    return data


def pacific_to_utc(day, hm: str) -> str:
    local = datetime(day.year, day.month, day.day, int(hm[:2]), int(hm[3:5]),
                     tzinfo=ZoneInfo("America/Vancouver"))
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def household_notes(hh: str) -> dict:
    data = call("Read", {"Note": {"Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
                                  "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": hh}}}},
                         "Compatibility": COMPAT})
    return {n["Key"]: n for n in data.get("Note", {}).get("Data", []) or []}


def create_note(hh: str, note_dt: str, manifest: dict) -> str:
    res = call("Create", {"Note": {"Data": {"Key": None, "ParentKey": hh,
                                            "DateTime": note_dt, "Text": NOTE_TEXT}},
                          "Compatibility": COMPAT})
    if res.get("Code", 0) != 0:
        sys.exit(f"Note create failed: {json.dumps(res)[:300]}")
    note_key = res["Note"]["Data"]["Key"]
    manifest["records"].append({"kind": "Note", "key": note_key, "label": LABEL})
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  note created, dated {note_dt}Z (UTC)")
    return note_key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-day", required=True, help="webinar date, YYYY-MM-DD")
    args = ap.parse_args()
    if not PAT:
        sys.exit("MAXIMIZER_PAT not set - run: set -a; source .env; set +a")

    demo_day = datetime.strptime(args.demo_day, "%Y-%m-%d").date()
    with open(MANIFEST) as f:
        manifest = json.load(f)
    hh = next(r["key"] for r in manifest["records"] if r["label"].startswith("Halloran Family"))
    existing = next((r["key"] for r in manifest["records"] if r.get("label") == LABEL), None)

    before = set(household_notes(hh))

    # 1. recent RESP statement note, ~3 weeks before the webinar (once only)
    note_dt = pacific_to_utc(demo_day - timedelta(days=23), "10:30")
    if existing:
        note_key = existing
        print("  RESP note already on the record (in manifest), not re-created")
    else:
        note_key = create_note(hh, note_dt, manifest)

    # 2. household RESP balance (the UDF stores on households; read back to confirm)
    res = call("Update", {"AbEntry": {"Data": {"Key": hh, RESP: BALANCE}}, "Compatibility": COMPAT})
    if res.get("Code", 0) != 0:
        sys.exit(f"RESP balance update failed: {json.dumps(res)[:300]}")

    # 3. verify + sweep audit notes this run generated
    problems = []
    notes = household_notes(hh)
    if note_key not in notes or not notes[note_key]["DateTime"].startswith(note_dt[:16]):
        problems.append(f"note readback: {notes.get(note_key)}")
    back = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, RESP: 1}},
                                     "Criteria": {"SearchQuery": {"Key": {"$EQ": hh}}}},
                         "Compatibility": COMPAT})["AbEntry"]["Data"][0].get(RESP)
    if back is None or float(back) != float(BALANCE):
        problems.append(f"RESP balance readback: {back}")
    swept = 0
    for key, n in notes.items():
        if key in before or key == note_key:
            continue
        if any(m in (n.get("Text") or "").lower() for m in ["changed from", "changed to", "modified", "hotlist task"]):
            swept += call("Delete", {"Note": {"Data": {"Key": key}}, "Compatibility": COMPAT}).get("Code", 0) == 0
        else:
            print(f"  ! unexpected new note left alone: {(n.get('Text') or '')[:80]!r}")

    print(f"  RESP balance read back: {back}")
    print(f"  audit notes swept: {swept}")
    if problems:
        print("PROBLEMS:\n  - " + "\n  - ".join(problems))
        sys.exit(1)
    print("Done, verified by read-back.")


if __name__ == "__main__":
    main()
