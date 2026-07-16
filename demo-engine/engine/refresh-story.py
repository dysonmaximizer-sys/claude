#!/usr/bin/env python3
"""Refresh a seeded story so it is true today (Phase 2 core).

Rolls every date-bearing record in a story's manifest forward by the number
of days since the story was last true (seed date, or last refresh). Relative
gaps are preserved: a call that was 5 weeks back stays 5 weeks back, the
demo-day appointment lands on the refresh day, open tasks stay in the near
future.

Day-shifting happens in PACIFIC time (America/Vancouver), then converts back
to UTC for the API. This keeps wall-clock times stable across daylight-saving
boundaries: a 2:45pm meeting stays 2:45pm whether the refresh crosses
March/November or not.

What rolls: InteractionLog StartDate/EndDate, Note DateTime, Appointment
StartDate/EndDate, Task DateTime, and the Date Last Contacted UDF on AbEntry
records where it is set. What NEVER rolls: birthdates (age-anchored) and any
other AbEntry field.

After writing, the script sweeps same-day audit notes Maximizer auto-logs
("Hotlist Task Modified..." etc.) and verifies every change with a read-back.

Usage:
  set -a; source .env; set +a       (from the repo root)
  python3 engine/refresh-story.py                      # refresh walk-in-ready
  python3 engine/refresh-story.py --story <slug>
  python3 engine/refresh-story.py --dry-run            # plan only, no writes
  python3 engine/refresh-story.py --as-of 2026-07-22 --dry-run
                                    # pretend today is a future date (testing)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
COMPAT = {"AbEntryKey": "2.0"}
PACIFIC = ZoneInfo("America/Vancouver")
UTC = ZoneInfo("UTC")
LASTCONTACT = "Udf/$TYPEID(60059)"

# Which datetime fields roll, per record kind. AbEntry is handled separately
# (only the Date Last Contacted UDF rolls; birthdates never do).
DATE_FIELDS = {
    "InteractionLog": ["StartDate", "EndDate"],
    "Note": ["DateTime"],
    "Appointment": ["StartDate", "EndDate"],
    "Task": ["DateTime"],
}

AUDIT_MARKERS = ["changed from", "field changed", "modified", "changed to",
                 "hotlist task", "opportunity created", "date last contacted"]


def call(endpoint: str, payload: dict) -> dict:
    r = requests.post(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    r.raise_for_status()
    return r.json()


def shift_utc_string(iso_z: str, days: int) -> str:
    """Shift a stored UTC datetime by N days IN PACIFIC, return naive-UTC string."""
    dt_utc = datetime.strptime(iso_z.replace("Z", ""), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    local = dt_utc.astimezone(PACIFIC)
    # same wall-clock time, N days later, in Pacific
    moved = (local + timedelta(days=days)).replace(tzinfo=None)
    moved = moved.replace(tzinfo=PACIFIC)
    return moved.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def read_record(kind: str, key: str, fields: list) -> Optional[dict]:
    data = call("Read", {
        kind: {"Scope": {"Fields": {f: 1 for f in ["Key"] + fields}},
               "Criteria": {"SearchQuery": {"Key": {"$EQ": key}}}},
        "Compatibility": COMPAT,
    })
    rows = data.get(kind, {}).get("Data", [])
    return rows[0] if rows else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", default="walk-in-ready")
    ap.add_argument("--dry-run", action="store_true", help="plan only, write nothing")
    ap.add_argument("--as-of", default=None, help="treat this date as today (testing)")
    args = ap.parse_args()

    manifest_path = os.path.join(REPO, "manifests", f"{args.story}-manifest.json")
    if not os.path.exists(manifest_path):
        sys.exit(f"No manifest at {manifest_path} - is the story seeded on this machine?")
    with open(manifest_path) as f:
        manifest = json.load(f)

    if not PAT and not args.dry_run:
        sys.exit("MAXIMIZER_PAT not set - run: set -a; source .env; set +a")

    today = (datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of
             else datetime.now(PACIFIC).date())
    anchor_str = manifest.get("refreshed") or manifest["created"]
    anchor = datetime.fromisoformat(anchor_str).date()
    days = (today - anchor).days

    print(f"Story: {args.story} | last true: {anchor} | target day: {today} | shift: {days} day(s)")
    if days == 0:
        print("Story is already true today. Nothing to do.")
        return
    if days < 0:
        sys.exit("Anchor date is in the future - refusing to roll a story backwards.")

    if not PAT:
        sys.exit("MAXIMIZER_PAT not set - run: set -a; source .env; set +a")

    failures = []
    changed = 0

    # ---- 1. roll datetime fields on story records
    for rec in manifest["records"]:
        kind = rec["kind"]
        if kind in DATE_FIELDS:
            fields = DATE_FIELDS[kind]
            row = read_record(kind, rec["key"], fields)
            if not row:
                failures.append(f"{kind} '{rec['label'][:40]}': not found in tenant")
                continue
            update = {"Key": rec["key"]}
            plan_bits = []
            for fname in fields:
                cur = row.get(fname)
                if not cur:
                    continue
                new = shift_utc_string(cur, days)
                update[fname] = new
                plan_bits.append(f"{fname} {cur} -> {new}")
            if len(update) == 1:
                continue
            print(f"  [{kind}] {rec['label'][:45]}: {'; '.join(plan_bits)}")
            if args.dry_run:
                continue
            res = call("Update", {kind: {"Data": update}, "Compatibility": COMPAT})
            if res.get("Code", 0) != 0:
                failures.append(f"{kind} '{rec['label'][:40]}': {json.dumps(res)[:200]}")
                continue
            back = read_record(kind, rec["key"], fields)
            for fname, want in [(k, v) for k, v in update.items() if k != "Key"]:
                got = (back or {}).get(fname, "")
                if not got.startswith(want[:16]):
                    failures.append(f"{kind} '{rec['label'][:40]}' readback: {fname}={got}, wanted {want}")
            changed += 1

        elif kind == "AbEntry":
            # only Date Last Contacted rolls; birthdates and all else stay put
            row = read_record(kind, rec["key"], [LASTCONTACT])
            val = (row or {}).get(LASTCONTACT)
            if not val:
                continue
            cur_date = datetime.strptime(val[:10], "%Y-%m-%d").date()
            new_date = (cur_date + timedelta(days=days)).strftime("%Y-%m-%d")
            print(f"  [AbEntry] {rec['label'][:45]}: Date Last Contacted {val[:10]} -> {new_date}")
            if args.dry_run:
                continue
            res = call("Update", {
                "AbEntry": {"Data": {"Key": rec["key"], LASTCONTACT: new_date}},
                "Compatibility": COMPAT,
            })
            if res.get("Code", 0) != 0:
                failures.append(f"AbEntry '{rec['label'][:40]}' last-contacted: {json.dumps(res)[:200]}")
            else:
                changed += 1

    if args.dry_run:
        print(f"\nDRY RUN complete - {changed or 'see'} planned changes above, nothing written.")
        return

    # ---- 2. sweep audit notes the run just generated
    story_note_keys = {r["key"] for r in manifest["records"] if r["kind"] == "Note"}
    today_str = datetime.now(PACIFIC).strftime("%Y-%m-%d")
    swept = 0
    for rec in [r for r in manifest["records"] if r["kind"] == "AbEntry"]:
        res = call("Read", {
            "Note": {"Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
                     "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": rec["key"]}}}},
            "Compatibility": COMPAT,
        })
        if res.get("Code", 0) != 0:
            failures.append(f"note sweep on '{rec['label'][:40]}' failed")
            continue
        for note in res.get("Note", {}).get("Data", []):
            if note["Key"] in story_note_keys:
                continue
            if not (note.get("DateTime") or "").startswith(today_str):
                continue
            text = (note.get("Text") or "").lower()
            if any(m in text for m in AUDIT_MARKERS):
                d = call("Delete", {"Note": {"Data": {"Key": note["Key"]}}, "Compatibility": COMPAT})
                if d.get("Code", 0) == 0:
                    swept += 1
                else:
                    failures.append(f"audit note delete failed on '{rec['label'][:40]}'")
            else:
                print(f"  ! unexpected note dated today on {rec['label'][:40]}: "
                      f"\"{(note.get('Text') or '')[:80]}\" - left alone, review manually")

    # ---- 3. stamp the manifest
    manifest["refreshed"] = today.isoformat()
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone: {changed} records rolled {days} day(s), {swept} audit note(s) swept.")
    if failures:
        print("PROBLEMS:")
        for x in failures:
            print(f"  - {x}")
        sys.exit(1)
    print("All changes verified by read-back.")


if __name__ == "__main__":
    main()
