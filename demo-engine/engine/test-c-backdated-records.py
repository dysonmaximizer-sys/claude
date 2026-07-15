#!/usr/bin/env python3
"""
Test C: Can the Octopus API create BACK-DATED activity records?
(Python 3.9-compatible version — replaces the copy in demo-engine-validation.)

What it does (against the DEMO tenant only):
  1. Finds a cast contact (default: Jameson Thomas) via AbEntry search.
  2. Creates a NOTE dated 90 days in the past.   <- the critical one
  3. Creates an APPOINTMENT dated 30 days in the past.
  4. Reads both back and prints the STORED dates.
  5. Prints created record keys. Run with --cleanup <key> to delete.

Setup:
  export MAXIMIZER_PAT="<personal access token for the DEMO tenant>"
  export MAXIMIZER_BASE_URL="https://api.maximizer.com/octopus"  # if regional
  pip3 install requests

Run:
  python3 test-c-backdated-records.py
  python3 test-c-backdated-records.py --contact "Lou" "Cameron"
  python3 test-c-backdated-records.py --cleanup "<record key>"
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests --break-system-packages")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")


def call(endpoint: str, payload: dict) -> dict:
    r = requests.post(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("Code", 0) != 0:
        print(f"!! API returned Code={data.get('Code')} for {endpoint}")
        print(json.dumps(data, indent=2)[:2000])
    return data


def find_abentry_key(first: str, last: str) -> str:
    payload = {
        "AbEntry": {
            "Scope": {"Fields": {"Key": 1, "FirstName": 1, "LastName": 1, "Type": 1}},
            "Criteria": {
                "SearchQuery": {
                    "$AND": [
                        {"FirstName": {"$EQ": first}},
                        {"LastName": {"$EQ": last}},
                    ]
                },
                "Top": 5,
            },
        },
        "Compatibility": {"AbEntryKey": "2.0"},
    }
    data = call("Read", payload)
    entries = data.get("AbEntry", {}).get("Data", [])
    if not entries:
        sys.exit(f"No AbEntry found for {first} {last} - is this the demo tenant?")
    for e in entries:
        print(f"  found: {e.get('FirstName')} {e.get('LastName')} ({e.get('Type')}) key={e.get('Key')}")
    return entries[0]["Key"]


def create_backdated_note(parent_key: str, days_ago: int = 90) -> Optional[str]:
    when = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%dT10:30:00")
    payload = {
        "Note": {
            "Data": {
                "Key": None,
                "ParentKey": parent_key,
                "DateTime": when,
                "Text": f"TEST-KIT back-dated note. Intended date: {when}. "
                        "If the Notes tab shows this date (not today), the API honours historical DateTimes.",
            }
        }
    }
    data = call("Create", payload)
    key = data.get("Note", {}).get("Data", {}).get("Key")
    print(f"  note created, intended DateTime={when}, key={key}")
    return key


def create_backdated_appointment(abentry_key: str, days_ago: int = 30) -> Optional[str]:
    day = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    payload = {
        "Appointment": {
            "Data": {
                "Key": None,
                "Subject": "TEST-KIT back-dated portfolio review",
                "StartDate": f"{day}T17:00:00Z",
                "EndDate": f"{day}T17:30:00Z",
                "Description": "Demo Engine validation - should appear 30 days in the past.",
                "AbEntries": [abentry_key],
            }
        },
        "Compatibility": {"AbEntryKey": "2.0"},
    }
    data = call("Create", payload)
    key = data.get("Appointment", {}).get("Data", {}).get("Key")
    print(f"  appointment created, intended StartDate={day}, key={key}")
    return key


def read_back_note(note_key: str) -> None:
    payload = {
        "Note": {
            "Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
            "Criteria": {"SearchQuery": {"Key": {"$EQ": note_key}}},
        }
    }
    data = call("Read", payload)
    for n in data.get("Note", {}).get("Data", []):
        print(f"  STORED note DateTime: {n.get('DateTime')}")


def read_back_appointment(appt_key: str) -> None:
    payload = {
        "Appointment": {
            "Scope": {"Fields": {"Key": 1, "Subject": 1, "StartDate": 1}},
            "Criteria": {"SearchQuery": {"Key": {"$EQ": appt_key}}},
        }
    }
    data = call("Read", payload)
    for a in data.get("Appointment", {}).get("Data", []):
        print(f"  STORED appointment StartDate: {a.get('StartDate')}")


def cleanup(key: str) -> None:
    obj = "Note" if key.startswith("Tm90Z") else "Appointment"
    call("Delete", {obj: {"Data": {"Key": key}}})
    print(f"  deleted {obj} {key}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contact", nargs=2, metavar=("FIRST", "LAST"), default=["Jameson", "Thomas"])
    ap.add_argument("--cleanup", metavar="KEY")
    args = ap.parse_args()

    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (PAT for the DEMO tenant, never production).")

    if args.cleanup:
        cleanup(args.cleanup)
        return

    first, last = args.contact
    print(f"1) Looking up {first} {last} ...")
    key = find_abentry_key(first, last)

    print("2) Creating back-dated note (90 days ago) ...")
    note_key = create_backdated_note(key)

    print("3) Creating back-dated appointment (30 days ago) ...")
    appt_key = create_backdated_appointment(key)

    print("4) Reading back stored dates ...")
    if note_key:
        read_back_note(note_key)
    if appt_key:
        read_back_appointment(appt_key)

    print("\nVerdict guide:")
    print("  - Stored dates match the intended past dates  -> timeline layer is BUILDABLE via API.")
    print("  - Stored dates are today                      -> API stamps 'now'; timeline realism needs another path.")
    print("  - Also check the record visually in Maximizer (Notes tab / Calendar / Timeline).")
    if note_key or appt_key:
        print("\nCleanup:")
        for k in (note_key, appt_key):
            if k:
                print(f'  python3 test-c-backdated-records.py --cleanup "{k}"')


if __name__ == "__main__":
    main()
