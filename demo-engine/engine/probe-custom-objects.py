#!/usr/bin/env python3
"""
Custom-object probe — READ-ONLY, writes nothing. Last stop in the hunt
for the FSE Accounts module (2026-07-21).

The full schema enumeration showed NO Accounts-style root among all 84
objects, but three roots can hide module data: /Custom, /CustomChild,
and /UdoDefinition (user-defined objects). If FSE's Accounts module is
a custom table, it lives behind these. This probe:

  1. Dumps the schema fields of all three roots.
  2. Reads the UdoDefinition rows (what custom objects are defined?).
  3. Reads a sample of Custom rows and prints them, so we can see
     whether they look like GIC / seg fund / annuity account records.

Paste the whole output back to Claude. Nothing is modified.

Run:    python3 engine/probe-custom-objects.py
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


def call(payload: dict) -> dict:
    time.sleep(PACE)
    r = requests.post(
        f"{BASE}/Read",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload, timeout=60,
    )
    if r.status_code == 429:
        wait = int(r.headers.get("Retry-After", "5"))
        print(f"  .. rate limited, waiting {wait}s")
        time.sleep(wait)
        return call(payload)
    r.raise_for_status()
    return r.json()


def schema_fields(root: str) -> list:
    data = call({
        "Schema": {"Scope": {"Fields": {"Key": 1, "Alias": 1, "Name": 1,
                                        "Type": 1, "Assignable": 1}},
                   "Criteria": {"SearchQuery": {"Key": {"$TREE": root}}}},
        "Compatibility": {"SchemaObject": "1.0"},
    })
    if data.get("Code", 0) != 0:
        print(f"  {root}: schema error Code={data.get('Code')}")
        return []
    return data.get("Schema", {}).get("Data", []) or []


def field_paths(fields: list, root: str, cap: int = 20) -> dict:
    scope = {}
    for f in fields[:cap]:
        k = str(f.get("Key") or "")
        short = k.replace(root + "/", "").lstrip("/")
        if short and "/" not in short:  # top-level simple fields only
            scope[short] = 1
    scope["Key"] = 1
    return scope


def read_rows(obj: str, scope: dict, limit: int = 20) -> list:
    data = call({
        obj: {"Scope": {"Fields": scope}, "OptionArgs": {"Limit": limit}},
        "Compatibility": {"AbEntryKey": "2.0"},
    })
    if data.get("Code", 0) != 0:
        print(f"  {obj} read rejected: Code={data.get('Code')} "
              f"{json.dumps(data.get('Msg', ''))[:200]}")
        return []
    return data.get(obj, {}).get("Data", []) or []


def main() -> None:
    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only). Load .env from the repo root.")

    for root in ("/UdoDefinition", "/Custom", "/CustomChild"):
        print("=" * 66)
        print(f"SCHEMA: {root}")
        print("=" * 66)
        fields = schema_fields(root)
        print(f"  {len(fields)} fields")
        for f in fields[:40]:
            print(f"  Key={f.get('Key')} | Name={f.get('Name')} | "
                  f"Type={f.get('Type')} | Assignable={f.get('Assignable')}")
        if len(fields) > 40:
            print(f"  ... and {len(fields) - 40} more")

        obj = root.lstrip("/")
        print(f"\n  -- sample {obj} rows --")
        rows = read_rows(obj, field_paths(fields, root))
        print(f"  {len(rows)} row(s) returned")
        for r in rows[:20]:
            print("  " + json.dumps(r, default=str)[:400])
        print()

    print("Probe complete. READ-ONLY - nothing was changed.")
    print("Paste this whole output back to Claude.")


if __name__ == "__main__":
    main()
