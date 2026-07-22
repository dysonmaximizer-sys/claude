#!/usr/bin/env python3
"""Seed "Sail Through Audits" - INSURANCE door variant (gated tour 3).

Distinct story from the FA-door tour of the same name (Renaud household,
CIRO): this one is Ingrid's regime - MGA and provincial, regulator kept
generic, insurance paper trail. Per Lewis 2026-07-22: the household is
the CHEN family, led by Michael Chen.

Cast:    Chen Family household (Guelph ON) - Michael (52, owns a small
         logistics business) + Grace (50). Served since 2018.
History: 8 annual insurance reviews (appointment + suitability note each
         year): term life placed 2018, CI added 2020, key-person cover
         2021, seg fund 2022 (+top-up 2025), DI discussed and DECLINED
         2023 with the decline documented - the compliance-gold detail.
         7 phone calls across the years, the latest 3 days ago about the
         MGA compliance review notice.
Today:   open task "Compile compliance file - Chen household (MGA
         review)" due +5 days.

Rules honoured: no CIRO anywhere; emails cannot be fabricated (calls +
notes carry correspondence); documents cannot be created via API (notes
reference signed documents; manual uploads listed in
docs/audits-insurance-manual-entries.md); owner fields set explicitly
(rule 10) - OWNER_USER, default MASTER "Barb Smith" until an Ingrid
user exists; times Pacific->UTC; manifest + audit sweep + read-backs.

Usage:
  set -a; source .env; set +a
  python3 engine/seed-sail-through-audits-insurance.py            # seed
  python3 engine/seed-sail-through-audits-insurance.py --cleanup
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
MANIFEST = os.path.join(REPO, "manifests", "sail-through-audits-insurance-manifest.json")
COMPAT = {"AbEntryKey": "2.0"}
PACIFIC = ZoneInfo("America/Vancouver")
UTC = ZoneInfo("UTC")
TODAY = datetime.now(PACIFIC)

OWNER_USER = os.environ.get("DEMO_OWNER_USER", "VXNlcglNQVNURVI=")  # rule 10

BDAY = "Udf/$TYPEID(124)"
SEG = "Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)"
LASTCONTACT = "Udf/$TYPEID(60059)"
LIFE_INS = "Udf/$NAME(WM_Client Info\\Additional Info\\Life Insurance)"
NEXT_INS_REVIEW = "Udf/$TYPEID(550)"
LAST_INS_REVIEW = "Udf/$TYPEID(842)"
LIFE_BENEFICIARY = "Udf/$NAME(Estate Planning\\Named Beneficiaries\\Do you have a named beneficiary for your life insurance policies)"


def call(endpoint: str, payload: dict) -> dict:
    for attempt in range(6):
        r = requests.post(f"{BASE}/{endpoint}",
                          headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                          json=payload, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 0)) or 10 * (attempt + 1))
            continue
        r.raise_for_status()
        time.sleep(0.35)
        return r.json()
    raise RuntimeError(f"rate-limited after 6 tries on {endpoint}")


def pac(days_ago: int, hm: str) -> str:
    day = TODAY - timedelta(days=days_ago)
    local = day.replace(hour=int(hm[:2]), minute=int(hm[3:5]), second=0, microsecond=0)
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def day_str(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def created_key(data: dict, obj: str) -> Optional[str]:
    return data.get(obj, {}).get("Data", {}).get("Key") if data.get("Code", 0) == 0 else None


def remember(manifest: dict, kind: str, key: Optional[str], label: str, quiet: bool = False) -> None:
    if key:
        manifest["records"].append({"kind": kind, "key": key, "label": label})
        if not quiet:
            print(f"  + {kind}: {label}")
    else:
        print(f"  ! FAILED: {label}")


def yd(years_ago: int, extra_days: int = 0) -> int:
    """Days-ago for 'about N years back', with stable per-year jitter."""
    return years_ago * 365 + (years_ago * 13) % 31 + extra_days


# (years_ago, suitability note; each year also gets a review appointment)
YEARLY = [
    (8, "Initial needs analysis completed and SIGNED (copy on file). Term life placed: "
        "Michael $750K T-20, Grace $400K T-20. Beneficiaries designated and recorded. "
        "Michael owns a logistics business (12 staff); key-person coverage discussed, "
        "parked for next year. Risk profiles documented."),
    (7, "Annual insurance review. Coverage confirmed suitable; no material change in "
        "circumstances. Premium banking updated (new business account). Beneficiary "
        "designations verified."),
    (6, "Annual insurance review. Needs analysis updated: recommended critical illness "
        "for Michael given self-employment income reliance. CI $150K placed for Michael; "
        "suitability rationale documented and signed."),
    (5, "Annual insurance review. Business grew to 19 staff; key-person coverage $500K "
        "placed on Michael per the updated needs analysis. Grace's coverage confirmed "
        "adequate at current income."),
    (4, "Annual insurance review. Segregated fund account opened for Grace, $120K initial "
        "deposit; risk tolerance questionnaire completed and on file. Insurance coverage "
        "unchanged, confirmed suitable."),
    (3, "Annual insurance review. Disability insurance discussed in depth for Michael; "
        "client DECLINED after reviewing quotes - rationale (retained earnings buffer in "
        "the business) documented and acknowledgment signed. Revisit at next review."),
    (2, "Needs analysis REFRESHED and signed (copy on file). Term renewal rates reviewed "
        "ahead of schedule at Michael's request; no changes made. All designations "
        "reconfirmed."),
    (1, "Annual insurance review. Seg fund top-up $40K (Grace). Beneficiaries reconfirmed. "
        "Grace asked about critical illness for herself - quote requested, pending. DI "
        "decline from 2023 revisited; position unchanged, noted."),
]

# (days_ago, subject, description, duration_min, direction 0=out 1=in)
CALLS = [
    (yd(6, 40), "Premium banking change - Michael",
     "Michael called to move premiums to the new business account. Updated with carrier; confirmation noted.", 6, 1),
    (yd(4, 25), "Seg fund statement question - Grace",
     "Grace asked how to read the market-value column on her first statement. Walked through it.", 9, 1),
    (yd(2, 55), "Renewal paperwork confirmation - Michael",
     "Confirmed receipt of signed renewal-review paperwork; copy filed to the household record.", 7, 0),
    (yd(1, -20), "CI quote follow-up - Grace",
     "Followed up on Grace's critical illness quote request; carrier illustrations ordered.", 11, 0),
    (60, "Meeting reschedule - Grace",
     "Grace moved the mid-year check-in by a week; calendar updated.", 4, 1),
    (21, "Premium receipt request - Michael",
     "Michael needed premium receipts for his accountant; sent from the record same day.", 5, 1),
    (3, "MGA compliance review notice - Michael",
     "Called Michael re: the MGA's compliance review of the household file. Walked him through "
     "what the reviewer sees; no action needed from him. File compilation under way.", 14, 0),
]


def seed() -> None:
    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}). Run --cleanup first.")
    manifest = {"story": "sail-through-audits-insurance",
                "created": TODAY.date().isoformat(), "records": []}

    print("== 1. Chen Family household ==")
    data = call("Create", {"AbEntry": {"Data": {
        "Key": None, "Type": "Household", "CompanyName": "Chen Family",
        "Address": {"AddressLine1": "88 Norwich St E", "City": "Guelph",
                    "StateProvince": "ON", "Country": "Canada", "ZipCode": "N1H 2G8"},
        "Phone1": {"Number": "(555) 010-7740"},
    }}, "Compatibility": COMPAT})
    hh = created_key(data, "AbEntry")
    remember(manifest, "AbEntry", hh, "Chen Family (Household)")
    if not hh:
        sys.exit(f"Household create failed: {json.dumps(data)[:300]}")

    contacts = {}
    for first, bday, email in [("Michael", "1974-05-08", "michael.chen@mail.test"),
                               ("Grace", "1976-01-19", "grace.chen@mail.test")]:
        data = call("Create", {"AbEntry": {"Data": {
            "Key": None, "Type": "Contact", "ParentKey": hh,
            "FirstName": first, "LastName": "Chen",
            "Email": {"Address": email}, "Phone1": {"Number": "(555) 010-7741"},
            BDAY: bday,
        }}, "Compatibility": COMPAT})
        contacts[first] = created_key(data, "AbEntry")
        remember(manifest, "AbEntry", contacts[first], f"{first} Chen")

    print("\n== 2. Eight years of reviews (appointment + suitability note each) ==")
    for years_ago, text in YEARLY:
        days = yd(years_ago)
        data = call("Create", {"Appointment": {"Data": {
            "Key": None, "Subject": "Annual insurance review - Chen household",
            "StartDate": pac(days, "10:00"), "EndDate": pac(days, "11:00"),
            "AbEntries": [hh],
        }}, "Compatibility": COMPAT})
        remember(manifest, "Appointment", created_key(data, "Appointment"),
                 f"Review appointment ({day_str(days)})", quiet=True)
        data = call("Create", {"Note": {"Data": {
            "Key": None, "ParentKey": hh, "DateTime": pac(days, "11:15"), "Text": text,
        }}, "Compatibility": COMPAT})
        remember(manifest, "Note", created_key(data, "Note"),
                 f"Review note ({day_str(days)})", quiet=True)
        print(f"  + {day_str(days)}: review appointment + note")

    print("\n== 3. Correspondence: seven calls across the years ==")
    for days_ago, subject, desc, dur, direction in CALLS:
        data = call("Create", {"InteractionLog": {"Data": {
            "Key": None, "Subject": subject, "Description": desc,
            "Type": "60001", "StartDate": pac(days_ago, "10:30"),
            "EndDate": pac(days_ago, f"10:{30 + dur}" if 30 + dur < 60 else "11:10"),
            "User": OWNER_USER, "AbEntryKey": hh, "Direction": direction,
        }}, "Compatibility": COMPAT})
        remember(manifest, "InteractionLog", created_key(data, "InteractionLog"), subject)

    print("\n== 4. Today's moment: the compliance-file task ==")
    data = call("Create", {"Task": {"Data": {
        "Key": None,
        "Activity": "Compile compliance file - Chen household (MGA review)",
        "DateTime": pac(-5, "17:00"), "AbEntryKey": hh, "AssignedTo": OWNER_USER,
    }}, "Compatibility": COMPAT})
    remember(manifest, "Task", created_key(data, "Task"), "Compliance-file task (due +5d)")

    print("\n== 5. Profiles ==")
    profile = [(hh, SEG, "1"), (hh, LASTCONTACT, day_str(3))]
    for who in ["Michael", "Grace"]:
        if contacts.get(who):
            profile += [(contacts[who], LIFE_INS, "2"),
                        (contacts[who], LIFE_BENEFICIARY, "2"),
                        (contacts[who], LAST_INS_REVIEW, day_str(yd(1))),
                        (contacts[who], NEXT_INS_REVIEW, day_str(-62))]
    for key, field, val in profile:
        res = call("Update", {"AbEntry": {"Data": {"Key": key, field: val}}, "Compatibility": COMPAT})
        if res.get("Code", 0) != 0:
            print(f"  ! UDF write failed ({field[:40]}): {json.dumps(res)[:150]}")
    print(f"  {len(profile)} profile fields set")

    print("\n== 6. Audit sweep + verify ==")
    today_str = TODAY.strftime("%Y-%m-%d")
    markers = ["changed from", "changed to", "modified", "hotlist task", "opportunity created",
               "created", "owner", "assigned", "insurance", "segmentation"]
    story_notes = {x["key"] for x in manifest["records"] if x["kind"] == "Note"}
    swept = 0
    for k in [hh] + [c for c in contacts.values() if c]:
        res = call("Read", {"Note": {"Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
                                     "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": k}}}}, "Compatibility": COMPAT})
        for note in res.get("Note", {}).get("Data", []):
            if note["Key"] in story_notes:
                continue
            if not (note.get("DateTime") or "").startswith(today_str):
                continue
            if any(m in (note.get("Text") or "").lower() for m in markers):
                d = call("Delete", {"Note": {"Data": {"Key": note["Key"]}}, "Compatibility": COMPAT})
                swept += d.get("Code", 0) == 0
    print(f"  audit notes swept: {swept}")

    counts = {}
    for rec in manifest["records"]:
        counts[rec["kind"]] = counts.get(rec["kind"], 0) + 1
    notes_back = call("Read", {"Note": {"Scope": {"Fields": {"Key": 1, "DateTime": 1}},
                                        "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": hh}}}}, "Compatibility": COMPAT})
    n_notes = len(notes_back.get("Note", {}).get("Data", []))
    print(f"  created: {json.dumps(counts)} | notes on household read back: {n_notes}")

    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nDone: {len(manifest['records'])} records. Manifest saved.")


def cleanup() -> None:
    if not os.path.exists(MANIFEST):
        sys.exit(f"No manifest at {MANIFEST} - nothing to clean.")
    with open(MANIFEST) as f:
        manifest = json.load(f)
    for rec in reversed(manifest["records"]):
        res = call("Delete", {rec["kind"]: {"Data": {"Key": rec["key"]}}, "Compatibility": COMPAT})
        print(f"  - {rec['label'][:50]}: {'deleted' if res.get('Code', 0) == 0 else 'FAILED'}")
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
