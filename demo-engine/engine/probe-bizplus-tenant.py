#!/usr/bin/env python3
"""READ-ONLY reconnaissance of the Business+ demo tenant. Writes NOTHING.

The engine's validated knowledge (CLAUDE.md) is FSE-tenant-specific:
UDF type IDs, pick-list values, users, modules. This probe discovers the
equivalent facts for the Business+ tenant so stories can be designed
against what actually exists there. Findings go to
docs/bizplus-tenant.md (this script prints; Claude writes the doc).

Run with the Business+ env loaded:
  set -a; source bizplus.env; set +a
  python3 demo-engine/engine/probe-bizplus-tenant.py
"""

import json
import os
import sys
import time
from typing import Optional

import requests

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
COMPAT = {"AbEntryKey": "2.0"}


def call(endpoint: str, payload: dict) -> dict:
    for attempt in range(6):
        r = requests.post(f"{BASE}/{endpoint}",
                          headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                          json=payload, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 0)) or 10 * (attempt + 1))
            continue
        if r.status_code in (401, 403):
            sys.exit(f"AUTH FAILED ({r.status_code}): token not accepted. Check bizplus.env "
                     "(placeholder still there? wrong tenant? different base URL?)")
        r.raise_for_status()
        time.sleep(0.35)
        return r.json()
    raise RuntimeError(f"rate-limited after 6 tries on {endpoint}")


def main() -> None:
    if not PAT or "PASTE-YOUR" in PAT:
        sys.exit("Business+ token not set. Load it with: set -a; source bizplus.env; set +a")

    print("== 1. Whoami / users (identifies the tenant and the rule-10 owner options) ==")
    res = call("Read", {"User": {"Scope": {"Fields": {"Key": 1, "DisplayName": 1, "FirstName": 1, "LastName": 1}},
                                 "Criteria": {"SearchQuery": {"LastName": {"$LIKE": "%"}}},
                                 "Options": {"Limit": 50}}, "Compatibility": COMPAT})
    users = res.get("User", {}).get("Data", [])
    for u in users:
        print(f"  {u.get('Key')} | {u.get('DisplayName')} | {u.get('FirstName')} {u.get('LastName')}")
    lewis = [u for u in users if "dyson" in json.dumps(u).lower() or "lewis" in json.dumps(u).lower()]
    if lewis:
        print(f"  !! RULE 10 ALERT: {len(lewis)} user(s) carry Lewis's name - owners must avoid them.")

    print("\n== 2. Book size and shape ==")
    rows, seen = [], set()
    for t in ["Individual", "Contact", "Company", "Household"]:
        res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "Type": 1}},
                                        "Criteria": {"SearchQuery": {"Type": {"$EQ": t}}},
                                        "Options": {"Limit": 500}}, "Compatibility": COMPAT})
        for r_ in res.get("AbEntry", {}).get("Data", []):
            if r_["Key"] not in seen:
                seen.add(r_["Key"])
                rows.append(r_)
    by_type = {}
    for r_ in rows:
        by_type[r_.get("Type")] = by_type.get(r_.get("Type"), 0) + 1
    print(f"  unique entries: {len(rows)} | by type: {json.dumps(by_type)}")
    if len(rows) > 2000:
        print("  !! STOP-AND-CHECK: unexpectedly large book for a demo tenant (rule 1).")

    print("\n== 3. Schema roots (which modules exist here) ==")
    res = call("Read", {"Schema": {"Scope": {"Fields": {"Key": 1}},
                                   "Criteria": {"SearchQuery": {"Key": {"$TREE": "/"}}}},
               "Compatibility": {"SchemaObject": "1.0"}})
    roots = sorted({str(f.get("Key", "")).split("/")[1] for f in res.get("Schema", {}).get("Data", [])
                    if str(f.get("Key", "")).count("/") == 1})
    print(f"  {len(roots)} roots: {', '.join(roots)}")

    print("\n== 4. AbEntry UDF folders (is this a wealth schema or a plain B2B one?) ==")
    res = call("Read", {"Schema": {"Scope": {"Fields": {"Key": 1, "Alias": 1, "Name": 1, "Assignable": 1}},
                                   "Criteria": {"SearchQuery": {"Key": {"$TREE": "/AbEntry"}}}},
               "Compatibility": {"SchemaObject": "1.0"}})
    fields = res.get("Schema", {}).get("Data", [])
    folders = {}
    for f in fields:
        for a in (f.get("Alias") or []):
            s = str(a)
            if "$NAME(" in s and "\\" in s:
                folders[s.split("$NAME(")[1].split("\\")[0]] = folders.get(s.split("$NAME(")[1].split("\\")[0], 0) + 1
    print(f"  {len(fields)} AbEntry fields; UDF folders: {json.dumps(folders, indent=1)[:600]}")
    for probe_name in ["Segmentation", "Birthdate", "Life Insurance", "Next KYC Review"]:
        hit = [f for f in fields if probe_name.lower() in json.dumps(f).lower()]
        print(f"  '{probe_name}': {'FOUND' if hit else 'absent'}"
              + (f" -> {json.dumps((hit[0].get('Alias') or [])[:2])}" if hit else ""))

    print("\n== 5. Opportunity: processes and mandatory fields ==")
    res = call("Read", {"Opportunity": {"FieldOptions": {"SalesProcessKey": [{"Key": 1, "DisplayValue": 1}]}},
               "Compatibility": COMPAT})
    procs = res.get("Opportunity", {}).get("FieldOptions", {}).get("SalesProcessKey", []) or []
    print(f"  sales processes: {json.dumps(procs)[:400]}")

    print("\n== 6. Interaction types (can we log calls the same way?) ==")
    res = call("Read", {"InteractionLog": {"FieldOptions": {"Type": [{"Key": 1, "DisplayValue": 1}]}},
               "Compatibility": COMPAT})
    types = res.get("InteractionLog", {}).get("FieldOptions", {}).get("Type", []) or []
    print(f"  {json.dumps(types)[:400]}")

    print("\nRECON COMPLETE - nothing was written. Paste this output back if running manually.")


if __name__ == "__main__":
    main()
