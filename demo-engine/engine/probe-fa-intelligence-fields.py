#!/usr/bin/env python3
"""
FA Intelligence field probe — READ-ONLY, writes nothing.

The FA Intelligence > Upcoming Reviews page shows six renewal tiles that
are all zero (Managed Segregated Funds, Managed Mortgages, Group Benefits,
Managed Insurance Policies, GIC Expiry Date, Annuities End Date). The
engine has no validated field names for any of them. This probe discovers
what those tiles read from:

  1. Dumps the AbEntry schema tree and lists every field matching the
     renewal-tile vocabulary (GIC, annuity, mortgage, segregated, group
     benefit, insurance, renewal, expiry, maturity, account), with its
     Key, Alias, Type, and Assignable flag.
  2. Tries plausible non-AbEntry schema roots (Account, Policy, Holding,
     Asset, Investment) to see whether an Accounts-style object exists.

Paste the whole output back to Claude; the update script gets written
from it. Nothing here modifies the tenant.

Run:    python3 engine/probe-fa-intelligence-fields.py
"""

import json
import os
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
PACE = 0.35

TERMS = ["gic", "annuit", "mortgage", "segregated", "seg fund", "segfund",
         "group benefit", "insurance", "renewal", "expiry", "expire",
         "maturity", "mature", "policy", "account"]

ROOTS = ["/Account", "/Policy", "/Holding", "/Asset", "/Investment",
         "/InsurancePolicy", "/FinancialAccount"]


def call(payload: dict) -> dict:
    time.sleep(PACE)
    r = requests.post(
        f"{BASE}/Read",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    if r.status_code == 429:
        wait = int(r.headers.get("Retry-After", "5"))
        print(f"  .. rate limited, waiting {wait}s")
        time.sleep(wait)
        return call(payload)
    r.raise_for_status()
    return r.json()


def schema_tree(root: str) -> list:
    data = call({
        "Schema": {
            "Scope": {"Fields": {"Key": 1, "Alias": 1, "Name": 1, "Type": 1, "Assignable": 1}},
            "Criteria": {"SearchQuery": {"Key": {"$TREE": root}}},
        },
        "Compatibility": {"SchemaObject": "1.0"},
    })
    if data.get("Code", 0) != 0:
        print(f"  root {root}: error Code={data.get('Code')} "
              f"{json.dumps(data.get('Msg', ''))[:150]}")
        return []
    return data.get("Schema", {}).get("Data", []) or []


def main() -> None:
    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only). Load .env from the repo root.")

    print("=" * 70)
    print("1) AbEntry schema: fields matching renewal-tile vocabulary")
    print("=" * 70)
    fields = schema_tree("/AbEntry")
    print(f"  ({len(fields)} AbEntry fields total)\n")
    seen = set()
    for f in fields:
        blob = json.dumps(f).lower()
        matched = [t for t in TERMS if t in blob]
        if not matched:
            continue
        key = f.get("Key")
        if key in seen:
            continue
        seen.add(key)
        print(f"  MATCH [{', '.join(matched)}]")
        print(f"    Key={key}")
        print(f"    Alias={f.get('Alias')} | Name={f.get('Name')}")
        print(f"    Type={f.get('Type')} | Assignable={f.get('Assignable')}")
    if not seen:
        print("  -- no AbEntry fields matched; the tiles likely read another object --")

    print()
    print("=" * 70)
    print("2) Non-AbEntry schema roots (do Accounts-style objects exist?)")
    print("=" * 70)
    for root in ROOTS:
        rows = schema_tree(root)
        if rows:
            print(f"\n  root {root}: EXISTS, {len(rows)} fields. First 15:")
            for f in rows[:15]:
                print(f"    Key={f.get('Key')} | Name={f.get('Name')} | "
                      f"Type={f.get('Type')} | Assignable={f.get('Assignable')}")
        else:
            print(f"  root {root}: nothing")

    print("\nProbe complete. READ-ONLY - nothing was changed.")
    print("Paste this whole output back to Claude.")


if __name__ == "__main__":
    main()
