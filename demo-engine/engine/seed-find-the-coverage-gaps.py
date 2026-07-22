#!/usr/bin/env python3
"""Seed the "Find the Coverage Gaps" story (Insurance door, gated tour 2).

What this seeds (all API-honest; see the accuracy notes in the story spec):

1. The Tremblay Family household (tour step 4's hero): Marc + Sophie + two
   kids, strong life coverage ON RECORD (Life Insurance = Yes, insurance
   needs review notes), an RESP balance, and a RECORDED-BUT-DEFERRED
   CI/DI conversation - the honest version of "no critical illness or
   disability in sight". Plus the working artifacts: a call, a task, and
   an open "Family protection review" opportunity.
2. Five existing cast clients dressed with honest gap signals so step 3's
   filtered list has rows: Life Insurance = Yes, Last Insurance Needs
   Review 12-30 months back, Next Insurance Needs Review inside the next
   1-3 months (kept inside the calendar year so review lists include
   them). Prior UDF values are captured in the manifest under
   "modified" so cleanup can restore them.

What this CANNOT seed (Accounts module is API-invisible, CLAUDE.md):
actual policy rows - term amounts, conversion windows, seg funds. Those
are manual UI entries; see docs/coverage-gaps-manual-policies.md.

Usage:
  set -a; source .env; set +a
  python3 engine/seed-find-the-coverage-gaps.py            # seed
  python3 engine/seed-find-the-coverage-gaps.py --cleanup  # remove + restore
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
MANIFEST = os.path.join(REPO, "manifests", "find-the-coverage-gaps-manifest.json")
COMPAT = {"AbEntryKey": "2.0"}
PACIFIC = ZoneInfo("America/Vancouver")
UTC = ZoneInfo("UTC")

# validated UDF paths (see CLAUDE.md)
BDAY = "Udf/$TYPEID(124)"
SEG = "Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)"
LASTCONTACT = "Udf/$TYPEID(60059)"
LIFE_INS = "Udf/$NAME(WM_Client Info\\Additional Info\\Life Insurance)"      # enum: 2=Yes, 1=No
NEXT_INS_REVIEW = "Udf/$TYPEID(550)"   # Next Insurance Needs Review (date)
LAST_INS_REVIEW = "Udf/$TYPEID(842)"   # Last Insurance Needs Review (date)
RESP_BAL = "Udf/$NAME(WM_KYC etc.\\Balance Sheet\\Liquid\\RESP)"             # currency
LIFE_BENEFICIARY = "Udf/$NAME(Estate Planning\\Named Beneficiaries\\Do you have a named beneficiary for your life insurance policies)"  # 2=Yes
INS_OBJECTIVE = "Udf/$NAME(Financial Planning\\Financial Objectives (1 - low, 5 - high)\\Evaluate or Initiate an insurance plan)"       # 1-5

TODAY = datetime.now(PACIFIC)

# clients never to touch, and story-slot names left to their own stories
EXCLUDE_NAMES = ["sokolov", "renaud", "tremblay", "bill graham", "jameson thomas",
                 "lou cameron", "nancy cameron", "celene smith", "wilson poulin",
                 "melissa myles", "lou harris", "bozik"]


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


def pac(days_offset: int, hm: str) -> str:
    day = TODAY + timedelta(days=days_offset)
    local = day.replace(hour=int(hm[:2]), minute=int(hm[3:5]), second=0, microsecond=0)
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def day(days_offset: int) -> str:
    return (TODAY + timedelta(days=days_offset)).strftime("%Y-%m-%d")


def created_key(data: dict, obj: str) -> Optional[str]:
    return data.get(obj, {}).get("Data", {}).get("Key") if data.get("Code", 0) == 0 else None


def remember(manifest: dict, kind: str, key: Optional[str], label: str) -> None:
    if key:
        manifest["records"].append({"kind": kind, "key": key, "label": label})
        print(f"  + {kind}: {label}")
    else:
        print(f"  ! FAILED: {label}")


def seed() -> None:
    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}). Run --cleanup first.")
    manifest = {"story": "find-the-coverage-gaps",
                "created": TODAY.date().isoformat(), "records": [], "modified": []}

    print("== 1. Tremblay Family household ==")
    data = call("Create", {"AbEntry": {"Data": {
        "Key": None, "Type": "Household", "CompanyName": "Tremblay Family",
        "Address": {"AddressLine1": "7355 Inlet Dr", "City": "Burnaby",
                    "StateProvince": "BC", "Country": "Canada", "ZipCode": "V5A 1C1"},
        "Phone1": {"Number": "(555) 010-7730"},
    }}, "Compatibility": COMPAT})
    hh = created_key(data, "AbEntry")
    remember(manifest, "AbEntry", hh, "Tremblay Family (Household)")
    if not hh:
        sys.exit(f"Household create failed: {json.dumps(data)[:300]}")

    contacts = {}
    for first, bday, email in [("Marc", "1984-03-14", "marc.tremblay@mail.test"),
                               ("Sophie", "1986-09-02", "sophie.tremblay@mail.test"),
                               ("Leo", "2017-02-11", None),
                               ("Chloe", "2020-05-23", None)]:
        payload = {"Key": None, "Type": "Contact", "ParentKey": hh,
                   "FirstName": first, "LastName": "Tremblay",
                   "Phone1": {"Number": "(555) 010-7731"}, BDAY: bday}
        if email:
            payload["Email"] = {"Address": email}
        data = call("Create", {"AbEntry": {"Data": payload}, "Compatibility": COMPAT})
        contacts[first] = created_key(data, "AbEntry")
        remember(manifest, "AbEntry", contacts[first], f"{first} Tremblay")

    print("\n== 2. Coverage profile (household + adults) ==")
    # one UDF per update call - multi-field UDF writes are unproven; stay validated
    # review-date UDFs are PERSON-level: they silently no-op on households
    # (validated 2026-07-22), so they go on the adults, not the household
    profile = [
        (hh, SEG, "2"), (hh, RESP_BAL, 38000),
        (hh, LASTCONTACT, day(-36)),
    ]
    for who in ["Marc", "Sophie"]:
        if contacts.get(who):
            profile += [(contacts[who], LIFE_INS, "2"),
                        (contacts[who], LIFE_BENEFICIARY, "2"),
                        (contacts[who], INS_OBJECTIVE, "4"),
                        (contacts[who], LAST_INS_REVIEW, day(-430)),
                        (contacts[who], NEXT_INS_REVIEW, day(21))]
    for key, field, val in profile:
        res = call("Update", {"AbEntry": {"Data": {"Key": key, field: val}}, "Compatibility": COMPAT})
        if res.get("Code", 0) != 0:
            print(f"  ! UDF write failed ({field[:40]}): {json.dumps(res)[:150]}")
    print(f"  {len(profile)} profile fields set")

    print("\n== 3. History: the recorded-but-deferred CI/DI gap ==")
    data = call("Create", {"Note": {"Data": {
        "Key": None, "ParentKey": hh, "DateTime": pac(-430, "14:00"),
        "Text": "Insurance needs review (in person). Term life in place for both: Marc $500K "
                "T-20, Sophie $350K T-20, beneficiaries current. Discussed adding critical "
                "illness and disability coverage; Marc self-employed since January, so income "
                "protection matters more now. Family chose to defer - revisit at next review. "
                "RESP on track for Leo and Chloe.",
    }}, "Compatibility": COMPAT})
    remember(manifest, "Note", created_key(data, "Note"), "Insurance review note (CI/DI deferred)")

    data = call("Create", {"InteractionLog": {"Data": {
        "Key": None,
        "Subject": "Call from Sophie - what happens if Marc can't work",
        "Description": "Sophie called while renewing the mortgage: asked directly what the plan "
                       "is if Marc is off work for six months. No disability coverage in place. "
                       "Promised options ahead of the review.",
        "Type": "60001", "StartDate": pac(-36, "10:40"), "EndDate": pac(-36, "10:52"),
        "User": "$CURRENTUSER()", "AbEntryKey": hh, "Direction": 1,
    }}, "Compatibility": COMPAT})
    remember(manifest, "InteractionLog", created_key(data, "InteractionLog"), "Sophie's DI question call")

    data = call("Create", {"Task": {"Data": {
        "Key": None, "Activity": "Prepare CI and DI options for the Tremblay review",
        "DateTime": pac(10, "17:00"), "AbEntryKey": hh,
    }}, "Compatibility": COMPAT})
    remember(manifest, "Task", created_key(data, "Task"), "CI/DI options task")

    data = call("Create", {"Opportunity": {"Data": {
        "Key": None, "AbEntryKey": hh,
        "Objective": "Family protection review - CI and DI",
        "Description": "Life coverage solid; CI/DI deferred at last review and Sophie has now "
                       "asked directly. Marc self-employed. Present options at the review.",
        "Status": 2, "ForecastRevenue": 3600, "CloseDate": pac(45, "12:00") + "Z",
    }}, "Compatibility": COMPAT})
    remember(manifest, "Opportunity", created_key(data, "Opportunity"), "Family protection review opportunity")

    print("\n== 4. Gap-list supporting clients (5 existing, priors captured) ==")
    rows, seen = [], set()
    for t in ["Individual", "Contact"]:
        res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "FirstName": 1, "LastName": 1,
                                                             LIFE_INS: 1, NEXT_INS_REVIEW: 1, LAST_INS_REVIEW: 1}},
                                        "Criteria": {"SearchQuery": {"Type": {"$EQ": t}}},
                                        "Options": {"Limit": 500}}, "Compatibility": COMPAT})
        for r_ in res.get("AbEntry", {}).get("Data", []):
            if r_["Key"] in seen:
                continue
            seen.add(r_["Key"])
            nm = f"{r_.get('FirstName') or ''} {r_.get('LastName') or ''}".strip()
            if nm and not any(x in nm.lower() for x in EXCLUDE_NAMES):
                rows.append((nm, r_))
    rows.sort(key=lambda x: x[1]["Key"])
    picks = rows[:5]
    spread = [(-380, 35), (-540, 60), (-395, 80), (-760, 25), (-410, 50)]
    for (nm, r_), (last_off, next_off) in zip(picks, spread):
        manifest["modified"].append({"key": r_["Key"], "label": nm, "prior": {
            LIFE_INS: r_.get(LIFE_INS), NEXT_INS_REVIEW: r_.get(NEXT_INS_REVIEW),
            LAST_INS_REVIEW: r_.get(LAST_INS_REVIEW)}})
        for field, val in [(LIFE_INS, "2"), (LAST_INS_REVIEW, day(last_off)), (NEXT_INS_REVIEW, day(next_off))]:
            res = call("Update", {"AbEntry": {"Data": {"Key": r_["Key"], field: val}}, "Compatibility": COMPAT})
            if res.get("Code", 0) != 0:
                print(f"  ! {nm}: write failed on {field[:35]}")
        print(f"  ~ {nm}: life=Yes, last review {day(last_off)}, next {day(next_off)}")

    print("\n== 5. Audit-note sweep + verify ==")
    today_str = TODAY.strftime("%Y-%m-%d")
    markers = ["changed from", "changed to", "modified", "hotlist task", "opportunity created",
               "insurance", "segmentation", "life"]
    swept = 0
    story_notes = {x["key"] for x in manifest["records"] if x["kind"] == "Note"}
    touched = [hh] + [c for c in contacts.values() if c] + [m["key"] for m in manifest["modified"]]
    for k in touched:
        res = call("Read", {"Note": {"Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
                                     "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": k}}}}, "Compatibility": COMPAT})
        for note in res.get("Note", {}).get("Data", []):
            if note["Key"] in story_notes or not (note.get("DateTime") or "").startswith(today_str):
                continue
            if any(m in (note.get("Text") or "").lower() for m in markers):
                d_ = call("Delete", {"Note": {"Data": {"Key": note["Key"]}}, "Compatibility": COMPAT})
                swept += d_.get("Code", 0) == 0
    print(f"  audit notes swept: {swept}")

    back = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, LIFE_INS: 1 if False else 1, SEG: 1, RESP_BAL: 1, NEXT_INS_REVIEW: 1, LAST_INS_REVIEW: 1}},
                                     "Criteria": {"SearchQuery": {"Key": {"$EQ": hh}}}}, "Compatibility": COMPAT})
    print("  household read-back:", json.dumps(back.get("AbEntry", {}).get("Data", []))[:300])

    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nDone: {len(manifest['records'])} records created, {len(manifest['modified'])} cast clients dressed. Manifest saved.")


def cleanup() -> None:
    if not os.path.exists(MANIFEST):
        sys.exit(f"No manifest at {MANIFEST} - nothing to clean.")
    with open(MANIFEST) as f:
        manifest = json.load(f)
    for m in manifest.get("modified", []):  # restore cast priors first
        data = {"Key": m["key"]}
        for field, val in m["prior"].items():
            res = call("Update", {"AbEntry": {"Data": {"Key": m["key"], field: val}}, "Compatibility": COMPAT})
        print(f"  ~ restored priors: {m['label']}")
    for rec in reversed(manifest.get("records", [])):
        res = call("Delete", {rec["kind"]: {"Data": {"Key": rec["key"]}}, "Compatibility": COMPAT})
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
