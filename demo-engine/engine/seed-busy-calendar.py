#!/usr/bin/env python3
"""Seed a believable week of advisor appointments (busy-calendar story).

Creates ~14 appointments across the current business week plus early next
week on the demo advisor's calendar, linked to persistent cast members
where they exist. Tracked in manifests/busy-calendar-manifest.json so it
can be refreshed (refresh-story.py --story busy-calendar) or cleaned up
independently of any other story.

Known limitation, documented on purpose: refresh-story.py shifts by
calendar days, so a refresh that isn't a multiple of 7 days will land
weekday appointments on weekends. Refresh this story in 7-day steps, or
reseed it fresh (cleanup + run this again) for a new recording week.

Times below are intended Pacific wall-clock; converted to UTC on send.

Usage:
  set -a; source .env; set +a
  python3 engine/seed-busy-calendar.py            # seed
  python3 engine/seed-busy-calendar.py --cleanup  # delete everything it made
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import requests

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MANIFEST = os.path.join(REPO, "manifests", "busy-calendar-manifest.json")
COMPAT = {"AbEntryKey": "2.0"}
PACIFIC = ZoneInfo("America/Vancouver")
UTC = ZoneInfo("UTC")


def call(endpoint: str, payload: dict) -> dict:
    for attempt in range(6):
        r = requests.post(f"{BASE}/{endpoint}",
                          headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                          json=payload, timeout=60)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 0)) or (10 * (attempt + 1))
            time.sleep(wait)
            continue
        r.raise_for_status()
        time.sleep(0.35)
        return r.json()
    raise RuntimeError(f"rate-limited after 6 tries on {endpoint}")


def pacific_utc(day: datetime, hm: str) -> str:
    local = day.replace(hour=int(hm[:2]), minute=int(hm[3:5]), second=0, microsecond=0,
                        tzinfo=PACIFIC)
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def find_contact(name: str) -> Optional[str]:
    first, last = name.rsplit(" ", 1)
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1}},
                                    "Criteria": {"SearchQuery": {"$AND": [
                                        {"FirstName": {"$EQ": first}}, {"LastName": {"$EQ": last}}]}},
                                    "Options": {"Limit": 2}}, "Compatibility": COMPAT})
    rows = res.get("AbEntry", {}).get("Data", [])
    return rows[0]["Key"] if rows else None


# (weekday offset from Monday of the current week, start, end, subject, cast name or None)
SLOTS = [
    (0, "09:30", "10:15", "Portfolio review - Wilson Poulin", "Wilson Poulin"),
    (0, "13:00", "13:45", "Intro call - referral from the Hendersons", None),
    (0, "16:00", "16:30", "Dealer back-office reconciliation", None),
    (1, "09:00", "09:45", "KYC review - Nancy Cameron", "Nancy Cameron"),
    (1, "11:00", "11:30", "GIC renewal options - Lou Harris", "Lou Harris"),
    (1, "14:00", "15:00", "Quarterly planning block", None),
    (2, "10:00", "10:45", "RRIF conversion review - Celene Smith", "Celene Smith"),
    (2, "15:30", "16:00", "Compliance file check", None),
    (3, "09:00", "09:30", "Morning prep - client files", None),
    (3, "11:15", "12:00", "Estate planning follow-up - Melissa Myles", "Melissa Myles"),
    (3, "16:30", "17:00", "Call notes and follow-ups", None),
    (4, "09:30", "10:15", "Annual review - Paula and Roberto Cameron", "Paula Cameron"),
    (4, "12:00", "13:00", "Lunch - accountant referral partner", None),
    (4, "14:30", "15:00", "New account paperwork", None),
    (7, "10:00", "10:45", "Retirement planning - Jameson Thomas", "Jameson Thomas"),
    (8, "09:30", "10:00", "Birthday call - Marina Sokolova", "Marina Sokolova"),
]


def seed() -> None:
    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}). Run --cleanup first so the calendar doesn't double up.")
    now_pacific = datetime.now(PACIFIC)
    monday = (now_pacific - timedelta(days=now_pacific.weekday())).replace(tzinfo=None)
    manifest = {"story": "busy-calendar", "created": now_pacific.date().isoformat(), "records": []}

    contact_cache = {}
    created = 0
    for dow, start, end, subject, who in SLOTS:
        day = monday + timedelta(days=dow)
        keys = []
        if who:
            if who not in contact_cache:
                contact_cache[who] = find_contact(who)
            if contact_cache[who]:
                keys = [contact_cache[who]]
        data = {"Key": None, "Subject": subject,
                "StartDate": pacific_utc(day, start), "EndDate": pacific_utc(day, end)}
        if keys:
            data["AbEntries"] = keys
        res = call("Create", {"Appointment": {"Data": data}, "Compatibility": COMPAT})
        key = res.get("Appointment", {}).get("Data", {}).get("Key")
        if res.get("Code", 0) == 0 and key:
            manifest["records"].append({"kind": "Appointment", "key": key, "label": subject})
            created += 1
            linked = "linked" if keys else "unlinked"
            print(f"  + {day.strftime('%a %b %d')} {start} {subject} ({linked})")
        else:
            print(f"  ! FAILED: {subject}: {json.dumps(res)[:150]}")

    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nDone: {created}/{len(SLOTS)} appointments created. Manifest: {MANIFEST}")


def cleanup() -> None:
    if not os.path.exists(MANIFEST):
        sys.exit(f"No manifest at {MANIFEST} - nothing to clean.")
    with open(MANIFEST) as f:
        manifest = json.load(f)
    for rec in reversed(manifest["records"]):
        res = call("Delete", {"Appointment": {"Data": {"Key": rec["key"]}}, "Compatibility": COMPAT})
        print(f"  - {rec['label']}: {'deleted' if res.get('Code', 0) == 0 else 'FAILED'}")
    os.remove(MANIFEST)
    print("Cleanup complete.")


if __name__ == "__main__":
    if not PAT:
        sys.exit("MAXIMIZER_PAT not set - run: set -a; source .env; set +a")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup", action="store_true")
    if ap.parse_args().cleanup:
        cleanup()
    else:
        seed()
