#!/usr/bin/env python3
"""Populate the Business+ Sales Intelligence dashboard: 2025 + 2026-YTD
deal history, and dress the 12 live pipeline deals for team reporting.

What the tiles need (validated 2026-07-23):
- Deals belong to REAL sales teams (defaults land in *Single User 65535,
  which team reports ignore) -> NA West / NA East / EMEA / ANZ.
- Won revenue THIS fiscal year -> won (Status 3) deals with 2026 close
  dates and ActualRevenue.
- YoY growth -> a full 2025 base year.
- Avg opportunity age -> StartDate set 30-120 days before close.
- Slicing realism -> RevenueType (New/Existing Business), Product,
  Category, spread across the five demo users (rule 10; never LDYSON).

Numbers tell a growth story: 2025 ~$560K won; 2026 YTD tracks ~20%
ahead. Amanda leads the leaderboard, Douglas close second.

PERMANENT: opportunity deletes are still Access-Denied for this PAT.
Manifest records everything; cleanup fallback = Status 5 + rename.

Run:
  set -a; source bizplus.env; set +a
  python3 demo-engine/engine/bizplus-seed-sales-history.py
"""

import hashlib
import json
import os
import sys
import time
from datetime import date, timedelta
from typing import Optional

import requests

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MANIFEST = os.path.join(REPO, "manifests", "bizplus", "sales-intelligence-history-manifest.json")
PIPELINE_MANIFEST = os.path.join(REPO, "manifests", "bizplus", "monday-pipeline-review-manifest.json")
COMPAT = {"AbEntryKey": "2.0"}

USERS = {"michelle": "VXNlcglNQVNURVI=", "amanda": "VXNlcglBQlJPV04=",
         "douglas": "VXNlcglEQ0VST04=", "jane": "VXNlcglKU01JVEg=", "david": "VXNlcglETVRD"}
TEAMS = {"nawest": "U2FsZXNUZWFtCTQ=", "naeast": "U2FsZXNUZWFtCTM=",
         "emea": "U2FsZXNUZWFtCTU=", "anz": "U2FsZXNUZWFtCTY="}
USER_TEAM = {"michelle": "nawest", "amanda": "nawest", "jane": "nawest",
             "douglas": "naeast", "david": "naeast"}
OBJECTIVES = ["Equipment order", "Service contract", "Software licences", "Annual renewal",
              "Consulting engagement", "Supply agreement", "Maintenance plan", "Upgrade package",
              "Fleet order", "Site services", "Training program", "Support contract"]


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


def h(key: str, mod: int) -> int:
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % mod


def created_key(data: dict) -> Optional[str]:
    return data.get("Opportunity", {}).get("Data", {}).get("Key") if data.get("Code", 0) == 0 else None


# (close_date, revenue, owner, status 3=won 4=lost) - the deal plan.
# 2025: four quarters, ~$560K won. 2026 YTD: growth to ~$545K by late July.
PLAN = [
    # 2025 Q1
    ("2025-01-24", 28000, "amanda", 3), ("2025-02-18", 34000, "douglas", 3), ("2025-03-11", 31000, "jane", 3),
    ("2025-02-06", 22000, "david", 4),
    # 2025 Q2
    ("2025-04-15", 30000, "amanda", 3), ("2025-05-08", 36000, "david", 3), ("2025-05-27", 29000, "douglas", 3),
    ("2025-06-19", 38000, "jane", 3), ("2025-06-05", 18000, "michelle", 4),
    # 2025 Q3
    ("2025-07-17", 41000, "amanda", 3), ("2025-08-12", 33000, "douglas", 3), ("2025-09-04", 39000, "david", 3),
    ("2025-09-23", 37000, "michelle", 3),
    # 2025 Q4
    ("2025-10-16", 44000, "amanda", 3), ("2025-11-06", 46000, "jane", 3), ("2025-11-25", 42000, "douglas", 3),
    ("2025-12-10", 52000, "michelle", 3), ("2025-12-04", 26000, "jane", 4),
    # 2026 YTD - growth
    ("2026-01-21", 42000, "amanda", 3), ("2026-01-29", 21000, "david", 3),
    ("2026-02-12", 47000, "douglas", 3), ("2026-02-25", 24000, "jane", 3),
    ("2026-03-10", 52000, "amanda", 3), ("2026-03-24", 33000, "michelle", 3),
    ("2026-03-05", 19000, "david", 4),
    ("2026-04-09", 49000, "douglas", 3), ("2026-04-22", 38000, "jane", 3),
    ("2026-05-07", 56000, "amanda", 3), ("2026-05-20", 41000, "david", 3),
    ("2026-05-12", 27000, "douglas", 4),
    ("2026-06-11", 58000, "douglas", 3), ("2026-06-24", 48000, "amanda", 3),
    ("2026-06-18", 31000, "jane", 4),
    ("2026-07-08", 46000, "jane", 3), ("2026-07-16", 44000, "michelle", 3),
    ("2026-07-03", 23000, "amanda", 4),
]


def main() -> None:
    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}). Deletes are blocked in this "
                 "tenant - do NOT double-seed. Talk to Claude before rerunning.")
    manifest = {"story": "sales-intelligence-history", "tenant": "bizplus",
                "created": date(2026, 7, 23).isoformat(),
                "opportunity_deletes_blocked": True, "records": [], "modified": []}

    print("== 1. Companies ==")
    rows, seen = [], set()
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "CompanyName": 1}},
                                    "Criteria": {"SearchQuery": {"Type": {"$EQ": "Company"}}},
                                    "Options": {"Limit": 200}}, "Compatibility": COMPAT})
    for r_ in res.get("AbEntry", {}).get("Data", []):
        if r_["Key"] not in seen and r_.get("CompanyName"):
            seen.add(r_["Key"])
            rows.append((r_.get("CompanyName"), r_["Key"]))
    rows.sort()
    print(f"  {len(rows)} companies available")

    print("\n== 2. Historical deals (won + lost, 2025-2026) ==")
    made = 0
    for i, (close, rev, owner, status) in enumerate(PLAN):
        name, ckey = rows[(i * 7) % len(rows)]
        obj = OBJECTIVES[h(close + name, len(OBJECTIVES))]
        start = (date.fromisoformat(close) - timedelta(days=30 + h(close, 91))).isoformat()
        payload = {
            "Key": None, "AbEntryKey": ckey,
            "Objective": obj, "Description": f"{obj} - {name}.",
            "Status": status, "ForecastRevenue": rev,
            "CloseDate": close, "StartDate": start,
            "Leader": USERS[owner], "SalesTeam": TEAMS[USER_TEAM[owner]],
            "RevenueType": "60002" if h(name, 3) == 0 else "60001",
            "Category": "2" if h(obj, 2) else "1",
            "Product": str(1 + h(obj + name, 6)),
        }
        if status == 3:
            payload["ActualRevenue"] = round(rev * (0.92 + h(close + "a", 17) / 100), -2)
        data = call("Create", {"Opportunity": {"Data": payload}, "Compatibility": COMPAT})
        key = created_key(data)
        if key:
            made += 1
            manifest["records"].append({"kind": "Opportunity", "key": key,
                                        "label": f"{name}: {obj} ({close}, {'won' if status == 3 else 'lost'}, ${rev/1000:.0f}K, {owner})"})
        else:
            print(f"  ! failed {name} {close}: {json.dumps(data)[:200]}")
    print(f"  created {made}/{len(PLAN)}")

    print("\n== 3. Dress the 12 live pipeline deals (teams, types, start dates) ==")
    pm = json.load(open(PIPELINE_MANIFEST))
    live = [r for r in pm["records"] if r["kind"] == "Opportunity"]
    for rec in live:
        cur = call("Read", {"Opportunity": {"Scope": {"Fields": {"Key": 1, "SalesTeam": 1, "Leader": 1, "CloseDate": 1}},
                                            "Criteria": {"SearchQuery": {"Key": {"$EQ": rec["key"]}}}}, "Compatibility": COMPAT})
        row = (cur.get("Opportunity", {}).get("Data") or [{}])[0]
        owner = next((k for k, v in USERS.items() if v == row.get("Leader")), "michelle")
        manifest["modified"].append({"key": rec["key"], "label": rec["label"][:50],
                                     "prior": {"SalesTeam": row.get("SalesTeam")}})
        start = (date(2026, 7, 23) - timedelta(days=21 + h(rec["key"], 70))).isoformat()
        upd = {"Key": rec["key"], "SalesTeam": TEAMS[USER_TEAM[owner]], "StartDate": start,
               "RevenueType": "60002" if h(rec["key"], 3) == 0 else "60001",
               "Category": "2" if h(rec["key"] + "c", 2) else "1",
               "Product": str(1 + h(rec["key"] + "p", 6))}
        res = call("Update", {"Opportunity": {"Data": upd}, "Compatibility": COMPAT})
        print(f"  {'ok ' if res.get('Code', 0) == 0 else '!! '} {rec['label'][:55]}")

    print("\n== 4. Verify ==")
    res = call("Read", {"Opportunity": {"Scope": {"Fields": {"Key": 1, "Status": 1, "CloseDate": 1, "SalesTeam": 1, "ActualRevenue": 1}},
                                        "Criteria": {"SearchQuery": {"Objective": {"$LIKE": "%"}}},
                                        "Options": {"Limit": 400}}, "Compatibility": COMPAT})
    opps = res.get("Opportunity", {}).get("Data", [])
    won26 = [o for o in opps if o.get("Status") == 3 and (o.get("CloseDate") or "").startswith("2026")]
    won25 = [o for o in opps if o.get("Status") == 3 and (o.get("CloseDate") or "").startswith("2025")]
    open_ = [o for o in opps if o.get("Status") == 2]
    noteam = [o for o in opps if o.get("Status") in (2, 3) and (o.get("CloseDate") or "") >= "2025"
              and o.get("SalesTeam") == "U2FsZXNUZWFtCTY1NTM1"]
    print(f"  won 2026: {len(won26)} (${sum(o.get('ActualRevenue') or 0 for o in won26)/1000:.0f}K actual)")
    print(f"  won 2025: {len(won25)} | open: {len(open_)} | 2025+ deals still teamless: {len(noteam)}")

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nDone. Manifest saved ({len(manifest['records'])} created, {len(manifest['modified'])} dressed).")


if __name__ == "__main__":
    if not PAT:
        sys.exit("MAXIMIZER_PAT not set - run: set -a; source bizplus.env; set +a")
    main()
