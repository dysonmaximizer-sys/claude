#!/usr/bin/env python3
"""
Walk In Ready — story seeder (Phase 1 validation).

Builds the Sokolov household and its timeline entirely via the Octopus API,
matching the Demo Centre hero tour script:

  Cast:      Sokolov Family household — Viktor (64), Marina (birthday in
             6 days), Daria (17, RESP maturing).
  History:   spring review call + meeting note (~14 weeks back),
             spring email exchange, June email with the OPEN RESP question,
             an open follow-up task due next week.
  Today:     the household review appointment at 2:45 PM.
  Optional:  one open opportunity (RESP maturity plan).

Everything is date-RELATIVE: run it the morning of a recording and
"last spoke in spring", "birthday next week", and "the 2:45 today" are
all true on camera. Every created key is written to a manifest file, so
  --cleanup   removes the whole story in reverse order.

Setup:  export MAXIMIZER_PAT="<demo tenant PAT>"        (never production)
        export MAXIMIZER_BASE_URL="..."                  (only if regional)
Run:    python3 seed-walk-in-ready.py
        python3 seed-walk-in-ready.py --cleanup

This is a VALIDATION script: some payload shapes (household creation,
birthdate field, interaction type ids) are documented loosely by Maximizer,
so each create tries the documented shape first, falls back where it can,
and prints exactly what worked and what didn't. Paste the output back to
Claude either way.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests --break-system-packages")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifests", "walk-in-ready-manifest.json")

TODAY = datetime.now()


def d(days_offset: int, hm: str = "10:00") -> str:
    """Local-naive datetime string, days_offset relative to today."""
    day = TODAY + timedelta(days=days_offset)
    return day.strftime(f"%Y-%m-%dT{hm}:00")


def call(endpoint: str, payload: dict, quiet: bool = False) -> dict:
    r = requests.post(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("Code", 0) != 0 and not quiet:
        print(f"  !! Code={data.get('Code')} on {endpoint}: {json.dumps(data)[:600]}")
    return data


def created_key(data: dict, obj: str) -> Optional[str]:
    return data.get(obj, {}).get("Data", {}).get("Key")


def remember(manifest: dict, kind: str, key: Optional[str], label: str) -> None:
    if key:
        manifest.setdefault("records", []).append({"kind": kind, "key": key, "label": label})
        print(f"  + {kind}: {label}")
    else:
        print(f"  - FAILED {kind}: {label}")


# ---------------------------------------------------------------- cast

def create_household(manifest: dict) -> Optional[str]:
    """Household create isn't explicitly documented; try the Company-style
    shape first, then a LastName-based shape."""
    for shape in (
        {"Key": None, "Type": "Household", "CompanyName": "Sokolov Family"},
        {"Key": None, "Type": "Household", "LastName": "Sokolov Family"},
    ):
        data = call("Create", {
            "AbEntry": {"Data": {**shape,
                "Address": {"AddressLine1": "412 Fairlawn Ave", "City": "Toronto",
                            "StateProvince": "ON", "Country": "Canada", "ZipCode": "M5M 1T8"},
                "Phone1": {"Number": "(555) 010-7710"},
            }},
            "Compatibility": {"AbEntryKey": "2.0"},
        }, quiet=True)
        key = created_key(data, "AbEntry")
        if key:
            print(f"  household created using shape: {list(shape.keys())[1:]} -> key={key}")
            remember(manifest, "AbEntry", key, "Sokolov Family (Household)")
            return key
        print(f"  household shape {list(shape.keys())[1:]} rejected: {json.dumps(data)[:300]}")
    return None


def create_contact(manifest: dict, parent_key: str, first: str, last: str,
                   birthdate: Optional[str], email: str) -> Optional[str]:
    base = {
        "Key": None,
        "Type": "Contact",
        "ParentKey": parent_key,
        "FirstName": first,
        "LastName": last,
        "Email": {"Address": email},
        "Phone1": {"Number": "(555) 010-7711"},
    }
    # Birthdate is the UDF "WM_KYC etc.\Personal\Birthdate" — confirmed
    # working as Udf/$TYPEID(124) on this tenant (validated 2026-07-15).
    attempts = []
    if birthdate:
        attempts.append({**base, "Udf/$TYPEID(124)": birthdate})
    attempts.append(base)

    for i, payload in enumerate(attempts):
        data = call("Create", {
            "AbEntry": {"Data": payload},
            "Compatibility": {"AbEntryKey": "2.0"},
        }, quiet=True)
        key = created_key(data, "AbEntry")
        if key:
            note = "" if (birthdate and i == 0) else " (WITHOUT birthdate - set it manually or tell Claude)"
            print(f"  contact {first} {last} created{note}")
            remember(manifest, "AbEntry", key, f"{first} {last}")
            return key
        if i == 0 and birthdate:
            print(f"  {first}: birthdate-shape rejected, retrying without ({json.dumps(data)[:200]})")
    print(f"  - FAILED contact {first} {last}")
    return None


# ---------------------------------------------------------------- timeline

def interaction_type_key(display_contains: str) -> Optional[str]:
    data = call("Read", {
        "InteractionLog": {"FieldOptions": {"Type": [{"Key": 1, "DisplayValue": 1}]}},
        "Compatibility": {"SchemaObject": "1.0"},
    }, quiet=True)
    for opt in data.get("InteractionLog", {}).get("FieldOptions", {}).get("Type", []) or []:
        if display_contains.lower() in str(opt.get("DisplayValue", "")).lower():
            return str(opt.get("Key"))
    return None


def create_interaction(manifest: dict, abentry_key: str, type_key: str, subject: str,
                       description: str, days_ago: int, duration_min: int = 0,
                       direction: int = 2) -> None:
    payload = {
        "Key": None,
        "Subject": subject,
        "Description": description,
        "Type": type_key,
        "StartDate": d(-days_ago, "10:00"),
        "EndDate": d(-days_ago, f"10:{duration_min:02d}" if duration_min else "10:00"),
        "User": "$CURRENTUSER()",
        "AbEntryKey": abentry_key,
        "Direction": direction,
    }
    data = call("Create", {"InteractionLog": {"Data": payload},
                           "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "InteractionLog", created_key(data, "InteractionLog"), subject)


def create_note(manifest: dict, parent_key: str, text: str, days_ago: int) -> None:
    data = call("Create", {"Note": {"Data": {
        "Key": None, "ParentKey": parent_key,
        "DateTime": d(-days_ago, "14:30"), "Text": text,
    }}})
    remember(manifest, "Note", created_key(data, "Note"), text[:50])


def create_task(manifest: dict, abentry_key: str, subject: str, due_in_days: int) -> None:
    """Open task = the 'RESP question still open' item. Schema validated
    2026-07-15: fields are Activity + DateTime (NOT Subject/DueDate/Description)."""
    data = call("Create", {"Task": {"Data": {
        "Key": None,
        "Activity": subject,
        "DateTime": d(due_in_days, "17:00"),
        "AbEntryKey": abentry_key,
    }}, "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "Task", created_key(data, "Task"), subject)


def create_appointment(manifest: dict, abentry_keys: list, subject: str) -> None:
    data = call("Create", {"Appointment": {"Data": {
        "Key": None, "Subject": subject,
        "StartDate": d(0, "14:45"), "EndDate": d(0, "15:30"),
        "Description": "Annual review - moved up from 3:00.",
        "AbEntries": abentry_keys,
    }}, "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "Appointment", created_key(data, "Appointment"), subject)


def create_opportunity(manifest: dict, abentry_key: str) -> None:
    data = call("Create", {"Opportunity": {"Data": {
        "Key": None, "AbEntryKey": abentry_key,
        "Objective": "RESP maturity transition plan",
        "Description": "Daria's RESP matures this year - transition options to present at review.",
        "Status": 2, "ForecastRevenue": 45000,
        "CloseDate": d(45, "12:00") + "Z",
    }}, "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "Opportunity", created_key(data, "Opportunity"), "RESP maturity transition plan")


# ---------------------------------------------------------------- main

def cleanup() -> None:
    if not os.path.exists(MANIFEST):
        sys.exit(f"No manifest at {MANIFEST} - nothing to clean.")
    with open(MANIFEST) as f:
        manifest = json.load(f)
    # delete children before parents: reverse creation order
    for rec in reversed(manifest.get("records", [])):
        data = call("Delete", {rec["kind"]: {"Data": {"Key": rec["key"]}}}, quiet=True)
        ok = data.get("Code", 0) == 0
        print(f"  {'deleted' if ok else 'FAILED to delete'} {rec['kind']}: {rec['label']}")
    os.remove(MANIFEST)
    print("Manifest removed.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup", action="store_true")
    args = ap.parse_args()

    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only).")

    if args.cleanup:
        cleanup()
        return

    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}). Run --cleanup first so the story doesn't double up.")

    manifest = {"story": "walk-in-ready", "created": TODAY.isoformat()}

    print("1) Creating the Sokolov household ...")
    hh = create_household(manifest)
    if not hh:
        _save(manifest)
        sys.exit("Household creation failed - paste this output to Claude before going further.")

    print("2) Creating household members ...")
    viktor = create_contact(manifest, hh, "Viktor", "Sokolov",
                            (TODAY - timedelta(days=64 * 365 + 120)).strftime("%Y-%m-%d"),
                            "viktor.sokolov@mail.test")
    marina_bday = (TODAY + timedelta(days=6)).replace(year=TODAY.year - 61).strftime("%Y-%m-%d")
    marina = create_contact(manifest, hh, "Marina", "Sokolova", marina_bday,
                            "marina.sokolova@mail.test")
    daria = create_contact(manifest, hh, "Daria", "Sokolova",
                           (TODAY - timedelta(days=17 * 365 + 200)).strftime("%Y-%m-%d"),
                           "daria.sokolova@mail.test")
    if not viktor:
        _save(manifest)
        sys.exit("Primary contact failed - stopping. Paste output to Claude.")

    print("3) Finding interaction type id (phone call) ...")
    # Emails/appointments/tasks CANNOT be created as interactions on this
    # tenant (types 60002-60004 blocked, validated 2026-07-15). Email
    # history only enters via real Outlook capture - use calls + notes.
    phone = interaction_type_key("phone")
    print(f"  phone type={phone}")

    print("4) Building the timeline ...")
    # Spring: ~14 weeks ago. "Last spoke in spring, file closed since."
    create_note(manifest, hh,
                "Spring review (in person). Rebalanced 60/40; discussed Daria's RESP maturing "
                "next year and options for unused room. Viktor asked about bridging to 65. "
                "All actions closed except RESP decision.", 98)
    if phone:
        create_interaction(manifest, hh, phone, "Spring review follow-up call",
                           "Confirmed rebalance executed; Marina asked for RESP paperwork.",
                           95, duration_min=18)
    # June: the open question the tour's step 3 calls out. Emails can't be
    # fabricated, so this lives as an incoming call + an open-item note.
    june_ago = int((TODAY - TODAY.replace(month=6, day=10)).days) if TODAY.month > 6 else 30
    if phone:
        create_interaction(manifest, hh, phone, "Call from Marina - RESP maturity question (open)",
                           "Marina asked whether to convert Daria's RESP to instalments for first-year "
                           "tuition or take the lump sum. NOT YET ANSWERED - open item for review.",
                           june_ago, duration_min=12, direction=1)
    create_note(manifest, hh,
                "OPEN ITEM: Marina asked (call) - RESP maturity: instalments vs lump sum for "
                "Daria's first year. Promised options at the annual review.", june_ago)
    create_task(manifest, hh, "Answer Marina's RESP maturity question (instalments vs lump sum)", 7)

    print("5) Today's meeting ...")
    attendees = [k for k in (viktor, marina) if k]
    create_appointment(manifest, attendees or [hh], "Sokolov household annual review")

    print("6) Open opportunity ...")
    create_opportunity(manifest, hh)

    _save(manifest)
    n = len(manifest.get("records", []))
    print(f"\nDone: {n} records created. Manifest: {MANIFEST}")
    print("Now open the Sokolov Family household in Maximizer and check it against the tour:")
    print("  - last conversations show as SPRING (not today)")
    print("  - the June RESP email reads as the open question")
    print("  - Marina's birthday shows as next week (if birthdate was accepted)")
    print("  - today's 2:45 PM review is on the calendar")
    print("  - the open task and opportunity appear as open items")
    print(f"\nRemove the whole story:  python3 seed-walk-in-ready.py --cleanup")


def _save(manifest: dict) -> None:
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main()
