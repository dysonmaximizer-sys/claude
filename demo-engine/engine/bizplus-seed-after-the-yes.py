#!/usr/bin/env python3
"""Seed "After the Yes" - Business+ sales door, gated tour 2.

What the API stages:
1. A "Client Onboarding" WORKFLOW TEMPLATE (6 sequential tasks, day
   offsets, AssignedToExpression "AccountManager" - mirroring the
   tenant's native template conventions exactly). The tour's step 3
   click starts THIS template.
2. The hero moment: Total Serve's deal won TODAY (the yes), clean and
   ready for the live click during capture - onboarding deliberately
   NOT started on it.
3. The onboarding cohort: four more wins across the last two weeks
   (plus the two existing mid-July wins from the history seed = six
   companies with fresh wins for step 5's "six in flight").

What the API cannot stage (validated: WorkflowInstance fields are
read-only): the six running instances. Lewis starts them in the UI
(~2 min, click list in the story spec); Claude then backdates one
instance's active task so one run shows "behind".

Accuracy gates honoured: the rep starts the workflow (no deal-won
automation is implied by any data), owners are demo users (rule 10),
teams set so reporting sees everything.

Run:
  set -a; source bizplus.env; set +a
  python3 demo-engine/engine/bizplus-seed-after-the-yes.py
"""

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
MANIFEST = os.path.join(REPO, "manifests", "bizplus", "after-the-yes-manifest.json")
COMPAT = {"AbEntryKey": "2.0"}
TODAY = date(2026, 7, 23)

USERS = {"michelle": "VXNlcglNQVNURVI=", "amanda": "VXNlcglBQlJPV04=",
         "douglas": "VXNlcglEQ0VST04=", "jane": "VXNlcglKU01JVEg=", "david": "VXNlcglETVRD"}
TEAMS = {"michelle": "U2FsZXNUZWFtCTQ=", "amanda": "U2FsZXNUZWFtCTQ=", "jane": "U2FsZXNUZWFtCTQ=",
         "douglas": "U2FsZXNUZWFtCTM=", "david": "U2FsZXNUZWFtCTM="}

ONBOARDING_TASKS = [
    (1, "Kickoff call - welcome the new client", 0),
    (2, "Collect signed paperwork and billing details", 1),
    (3, "Set up the account and provision services", 2),
    (4, "Deliver the kickoff training session", 3),
    (5, "Thirty-day check-in call", 25),
    (6, "Confirm onboarding complete and log the outcome", 3),
]

# (company, objective, revenue, close date, owner) - the recent-win cohort
COHORT = [
    ("Total Serve", "Managed services agreement", 54000, TODAY.isoformat(), "david"),  # THE HERO - won today
    ("Briazz", "Catering supply program", 26000, (TODAY - timedelta(days=3)).isoformat(), "amanda"),
    ("Multicerv", "Service contract", 31000, (TODAY - timedelta(days=6)).isoformat(), "douglas"),
    ("Sistemos", "Software licences", 22000, (TODAY - timedelta(days=10)).isoformat(), "jane"),
    ("Widdmann", "Equipment order", 19000, (TODAY - timedelta(days=13)).isoformat(), "david"),
]


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


def main() -> None:
    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}) - do not double-seed.")
    manifest = {"story": "after-the-yes", "tenant": "bizplus",
                "created": TODAY.isoformat(), "records": []}

    print("== 1. Client Onboarding workflow template ==")
    existing = call("Read", {"Workflow": {"Scope": {"Fields": {"Key": 1, "Name": 1}},
                                          "Criteria": {"SearchQuery": {"Name": {"$EQ": "Client Onboarding"}}}},
                    "Compatibility": COMPAT})
    if existing.get("Workflow", {}).get("Data", []):
        wf_key = existing["Workflow"]["Data"][0]["Key"]
        print("  template already exists - reusing")
    else:
        res = call("Create", {"Workflow": {"Data": {
            "Key": None, "Name": "Client Onboarding",
            "Description": "Runs the handoff after a closed deal: kickoff, setup, training, "
                           "and the thirty-day check-in, one task at a time.",
            "IsSequential": True, "HasStages": False, "Category": ["2"],
        }}, "Compatibility": COMPAT})
        wf_key = res.get("Workflow", {}).get("Data", {}).get("Key")
        if not wf_key:
            sys.exit(f"Workflow template create failed: {json.dumps(res)[:300]}")
        manifest["records"].append({"kind": "Workflow", "key": wf_key, "label": "Client Onboarding template"})
        print("  + template created")
        for seq, subject, offset in ONBOARDING_TASKS:
            res = call("Create", {"WorkflowTaskTemplate": {"Data": {
                "Key": None, "WorkflowKey": wf_key, "Sequence": seq, "Subject": subject,
                "DateOffsetUnit": 3, "DateOffsetValue": offset,
                "AssignedToExpression": "AccountManager",
            }}, "Compatibility": COMPAT})
            k = res.get("WorkflowTaskTemplate", {}).get("Data", {}).get("Key")
            if k:
                manifest["records"].append({"kind": "WorkflowTaskTemplate", "key": k, "label": f"{seq}. {subject}"})
                print(f"  + task {seq}: {subject}")
            else:
                print(f"  ! task {seq} failed: {json.dumps(res)[:200]}")

    print("\n== 2. The cohort wins (hero + 4 recent) ==")
    for name, objective, rev, close, owner in COHORT:
        comp = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1}},
                                         "Criteria": {"SearchQuery": {"CompanyName": {"$EQ": name}}}},
                    "Compatibility": COMPAT})
        ck = (comp.get("AbEntry", {}).get("Data") or [{}])[0].get("Key")
        if not ck:
            print(f"  ! company not found: {name}")
            continue
        start = (date.fromisoformat(close) - timedelta(days=48)).isoformat()
        res = call("Create", {"Opportunity": {"Data": {
            "Key": None, "AbEntryKey": ck, "Objective": objective,
            "Description": f"{objective} - {name}. Signed.",
            "Status": 3, "ForecastRevenue": rev, "ActualRevenue": rev,
            "CloseDate": close, "StartDate": start,
            "Leader": USERS[owner], "SalesTeam": TEAMS[owner],
            "RevenueType": "60001", "Category": "2", "Product": "5",
        }}, "Compatibility": COMPAT})
        k = res.get("Opportunity", {}).get("Data", {}).get("Key")
        if k:
            manifest["records"].append({"kind": "Opportunity", "key": k,
                                        "label": f"{name}: {objective} won {close} ({owner})"})
            print(f"  + {name}: won {close} (${rev/1000:.0f}K, {owner})")
        else:
            print(f"  ! {name} failed: {json.dumps(res)[:200]}")

    print("\n== 3. Verify template read-back ==")
    res = call("Read", {"WorkflowTaskTemplate": {"Scope": {"Fields": {"Key": 1, "Sequence": 1, "Subject": 1, "AssignedToExpression": 1}},
                                                 "Criteria": {"SearchQuery": {"WorkflowKey": {"$EQ": wf_key}}}},
               "Compatibility": COMPAT})
    rows = sorted(res.get("WorkflowTaskTemplate", {}).get("Data", []), key=lambda x: x.get("Sequence", 0))
    print(f"  template has {len(rows)} tasks:")
    for r_ in rows:
        print(f"    {r_.get('Sequence')}. {r_.get('Subject')} -> {r_.get('AssignedToExpression')}")

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nDone: {len(manifest['records'])} records. Manifest saved.")


if __name__ == "__main__":
    if not PAT:
        sys.exit("MAXIMIZER_PAT not set - run: set -a; source bizplus.env; set +a")
    main()
