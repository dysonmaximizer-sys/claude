#!/usr/bin/env python3
"""Seed "Monday pipeline review" - Business+ tenant. FIRST Business+ story.

A VP Sales (Michelle Boone) reviews the TEAM pipeline: 12 current
opportunities across five owners with deliberate review-moments baked in:
one hot deal closing Friday, one slipped close date still open, three
stale deals (no activity 4-6 weeks), the rest healthy at various depths.
Calls/notes/tasks give the active deals texture; the stale ones are
quiet on purpose - that silence is what the review surfaces.

Tenant facts honoured (docs/bizplus-tenant.md):
- Opportunity DELETE is Access-Denied for this PAT: creates are
  permanent until Lewis grants delete permission. Cleanup fallback =
  rename + Status 4. One pre-existing probe opportunity (Alpha Beta) is
  REPURPOSED as a story deal instead of deleted.
- Stages are per-deal instances; deals are created stage-less and get
  stages assigned in the UI (list in the story spec).
- Email interactions blocked (same as FSE): texture is calls + notes.
- Rule 10: every Leader/AssignedTo/User set explicitly; no LDYSON.

Run (Business+ env!):
  set -a; source bizplus.env; set +a
  python3 demo-engine/engine/bizplus-seed-monday-pipeline.py
"""

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
MANIFEST = os.path.join(REPO, "manifests", "bizplus", "monday-pipeline-review-manifest.json")
COMPAT = {"AbEntryKey": "2.0"}
PACIFIC = ZoneInfo("America/Vancouver")
UTC = ZoneInfo("UTC")
TODAY = datetime.now(PACIFIC)

USERS = {
    "michelle": "VXNlcglNQVNURVI=",   # Michelle Boone - the VP (Lewis's pick)
    "amanda": "VXNlcglBQlJPV04=",     # Amanda Brown
    "douglas": "VXNlcglEQ0VST04=",    # Douglas Ceron
    "jane": "VXNlcglKU01JVEg=",       # Jane Smith
    "david": "VXNlcglETVRD",          # David Canter
}
PROBE_STRAY_KEY = "T3Bwb3J0dW5pdHkJMjYwNzIzMjUxODE1NTMxNzIwMTA3Twkw"  # repurposed


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


def company_key(name: str) -> Optional[str]:
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1}},
                                    "Criteria": {"SearchQuery": {"CompanyName": {"$EQ": name}}},
                                    "Options": {"Limit": 2}}, "Compatibility": COMPAT})
    rows = res.get("AbEntry", {}).get("Data", [])
    return rows[0]["Key"] if rows else None


# (company, objective, revenue, close_days_from_today, owner, character)
DEALS = [
    ("Walley World", "Fleet equipment order", 85000, 2, "michelle", "hot - closes Friday"),
    ("Cyberdyne Systems", "Annual service contract renewal", 60000, -8, "douglas", "SLIPPED - close date last week, still open"),
    ("Magna Gases", "Cylinder tracking pilot", 24000, 30, "jane", "STALE - quiet 5 weeks"),
    ("Rhodes Furniture", "Showroom POS rollout", 18000, 25, "david", "STALE - quiet 4 weeks"),
    ("Bell Markets", "Store expansion fit-out", 32000, 40, "amanda", "STALE - quiet 6 weeks"),
    ("Webcom Business Services", "Managed IT services agreement", 45000, 21, "amanda", "active"),
    ("Delta Bike Company", "Wholesale supply program", 28000, 35, "jane", "active"),
    ("Gart Sports", "Team equipment contract", 52000, 28, "douglas", "active"),
    ("Quality Merchant Services", "Payment services agreement", 38000, 42, "michelle", "active"),
    ("Konsili", "Operations software - discovery", 15000, 56, "david", "early"),
    ("Excella", "Pilot order", 12000, 63, "jane", "early"),
    # Alpha Beta = repurposed probe record, handled separately
]

# (company, days_ago, subject, description, minutes, direction, owner)
CALLS = [
    ("Walley World", 1, "Final pricing call - Walley World",
     "Walked the fleet order pricing with their ops director. Verbal yes; paperwork promised for Friday.", 18, 0, "michelle"),
    ("Walley World", 6, "Fleet spec confirmation",
     "Confirmed quantities and delivery windows with purchasing.", 11, 1, "michelle"),
    ("Cyberdyne Systems", 12, "Renewal check-in",
     "Reached their office manager; decision maker travelling until next week. Renewal intent still positive.", 7, 0, "douglas"),
    ("Webcom Business Services", 3, "Scope review call",
     "Reviewed the managed services scope; they asked for a two-site option in the agreement.", 14, 1, "amanda"),
    ("Delta Bike Company", 7, "Wholesale terms discussion",
     "Discussed seasonal order volumes and payment terms.", 12, 0, "jane"),
    ("Quality Merchant Services", 4, "Requirements call",
     "Confirmed processing volumes and settlement timing requirements.", 16, 1, "michelle"),
    ("Konsili", 8, "Intro call - operations software",
     "First conversation; current process is spreadsheets plus a legacy tool. Discovery meeting booked.", 22, 0, "david"),
    ("Magna Gases", 36, "Pilot follow-up",
     "Left message re: cylinder tracking pilot next steps.", 3, 0, "jane"),
]

NOTES = [
    ("Walley World", 1, "Fleet order at verbal yes. Contract sent for signature; close set for Friday. "
                        "Delivery starts first week of August if signed on time."),
    ("Gart Sports", 2, "Revised team equipment proposal sent (added the junior program bundle). "
                       "They compare against one other supplier; decision expected within the month."),
    ("Cyberdyne Systems", 12, "Renewal slipped past its close date - decision maker away. "
                              "Intent positive but unconfirmed; timeline needs re-anchoring."),
    ("Bell Markets", 43, "Expansion fit-out quote delivered for the two new stores."),
    ("Rhodes Furniture", 29, "POS rollout demo done; waiting on their financing decision."),
]

# (company, days_from_today, activity, owner)
TASKS = [
    ("Walley World", 0, "Final pricing sign-off - Walley World fleet order", "michelle"),
    ("Cyberdyne Systems", 1, "Re-anchor renewal timeline with decision maker", "douglas"),
    ("Webcom Business Services", 2, "Send two-site option in revised agreement", "amanda"),
    ("Gart Sports", 3, "Follow up on revised team equipment proposal", "douglas"),
    ("Konsili", 1, "Send discovery meeting agenda and needs summary", "david"),
]


def seed() -> None:
    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}). This tenant cannot delete "
                 "opportunities - do NOT double-seed. Talk to Claude before rerunning.")
    manifest = {"story": "monday-pipeline-review", "tenant": "bizplus",
                "created": TODAY.date().isoformat(),
                "opportunity_deletes_blocked": True, "records": []}

    print("== 1. Resolve companies ==")
    keys = {}
    for name in {d[0] for d in DEALS} | {c[0] for c in CALLS} | {n[0] for n in NOTES} | {t[0] for t in TASKS} | {"Alpha Beta"}:
        keys[name] = company_key(name)
        if not keys[name]:
            sys.exit(f"Company not found: {name} - aborting before any writes.")
    print(f"  {len(keys)} companies resolved")

    print("\n== 2. Opportunities (11 new + 1 repurposed probe) ==")
    for name, objective, rev, close_off, owner, character in DEALS:
        data = call("Create", {"Opportunity": {"Data": {
            "Key": None, "AbEntryKey": keys[name], "Objective": objective,
            "Description": f"{objective} - {name}.",
            "Status": 2, "ForecastRevenue": rev, "CloseDate": day(close_off),
            "Leader": USERS[owner],
        }}, "Compatibility": COMPAT})
        remember(manifest, "Opportunity", created_key(data, "Opportunity"),
                 f"{name}: {objective} (${rev/1000:.0f}K, {character})")

    res = call("Update", {"Opportunity": {"Data": {
        "Key": PROBE_STRAY_KEY, "Objective": "Office refit supply",
        "Description": "Office refit supply - Alpha Beta.",
        "Status": 2, "ForecastRevenue": 21000, "CloseDate": day(26),
        "Leader": USERS["amanda"],
    }}, "Compatibility": COMPAT})
    if res.get("Code", 0) == 0:
        manifest["records"].append({"kind": "Opportunity", "key": PROBE_STRAY_KEY,
                                    "label": "Alpha Beta: Office refit supply (repurposed probe)"})
        print("  + Opportunity: Alpha Beta repurposed from stray probe")
    else:
        print(f"  ! probe repurpose failed: {json.dumps(res)[:200]}")

    print("\n== 3. Calls ==")
    for name, days_ago, subject, desc, mins, direction, owner in CALLS:
        end_min = 30 + mins
        data = call("Create", {"InteractionLog": {"Data": {
            "Key": None, "Subject": subject, "Description": desc,
            "Type": "60001", "StartDate": pac(-days_ago, "10:30"),
            "EndDate": pac(-days_ago, f"{10 + end_min // 60}:{end_min % 60:02d}"),
            "User": USERS[owner], "AbEntryKey": keys[name], "Direction": direction,
        }}, "Compatibility": COMPAT})
        remember(manifest, "InteractionLog", created_key(data, "InteractionLog"), subject)

    print("\n== 4. Notes ==")
    for name, days_ago, text in NOTES:
        data = call("Create", {"Note": {"Data": {
            "Key": None, "ParentKey": keys[name], "DateTime": pac(-days_ago, "15:00"), "Text": text,
        }}, "Compatibility": COMPAT})
        remember(manifest, "Note", created_key(data, "Note"), f"Note: {name} (-{days_ago}d)")

    print("\n== 5. Tasks ==")
    for name, days_off, activity, owner in TASKS:
        data = call("Create", {"Task": {"Data": {
            "Key": None, "Activity": activity, "DateTime": pac(days_off, "17:00"),
            "AbEntryKey": keys[name], "AssignedTo": USERS[owner],
        }}, "Compatibility": COMPAT})
        remember(manifest, "Task", created_key(data, "Task"), activity)

    print("\n== 6. Audit sweep + verify ==")
    today_str = TODAY.strftime("%Y-%m-%d")
    markers = ["changed from", "changed to", "modified", "hotlist task", "opportunity created",
               "created", "owner", "assigned"]
    story_notes = {x["key"] for x in manifest["records"] if x["kind"] == "Note"}
    swept = 0
    for k in set(keys.values()):
        res = call("Read", {"Note": {"Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
                                     "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": k}}}}, "Compatibility": COMPAT})
        for note in res.get("Note", {}).get("Data", []):
            if note["Key"] in story_notes or not (note.get("DateTime") or "").startswith(today_str):
                continue
            if any(m in (note.get("Text") or "").lower() for m in markers):
                d_ = call("Delete", {"Note": {"Data": {"Key": note["Key"]}}, "Compatibility": COMPAT})
                swept += d_.get("Code", 0) == 0
    print(f"  audit notes swept: {swept}")

    ok, bad = 0, 0
    for rec in manifest["records"]:
        if rec["kind"] != "Opportunity":
            continue
        res = call("Read", {"Opportunity": {"Scope": {"Fields": {"Key": 1, "Leader": 1, "Status": 1}},
                                            "Criteria": {"SearchQuery": {"Key": {"$EQ": rec["key"]}}}}, "Compatibility": COMPAT})
        row = (res.get("Opportunity", {}).get("Data") or [{}])[0]
        if row.get("Status") == 2 and row.get("Leader") in USERS.values():
            ok += 1
        else:
            bad += 1
            print(f"  !! verify failed: {rec['label'][:50]} -> {json.dumps(row)[:120]}")
    print(f"  opportunities verified: {ok} ok, {bad} bad")

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    counts = {}
    for rec in manifest["records"]:
        counts[rec["kind"]] = counts.get(rec["kind"], 0) + 1
    print(f"\nDone: {json.dumps(counts)}. Manifest saved (bizplus).")


if __name__ == "__main__":
    if not PAT:
        sys.exit("MAXIMIZER_PAT not set - run: set -a; source bizplus.env; set +a")
    seed()
