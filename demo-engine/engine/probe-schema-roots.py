#!/usr/bin/env python3
"""
Schema ROOT enumeration — READ-ONLY, writes nothing.

The renewal tiles ("Accounts - Upcoming Renewals") read the FSE Accounts
module, not AbEntry UDFs (proven 2026-07-21: verified GIC Expiry UDF
writes left the GIC tile at zero). The first probe guessed seven root
names and found none. This probe stops guessing: it asks the Schema for
EVERYTHING and prints every distinct top-level object the API exposes.

If an Accounts-style root exists under any name, this finds it. If it
does not appear here, the module has no API surface and the tiles can
only be fed through the Maximizer UI (or a dealer feed).

Paste the whole output back to Claude.

Run:    python3 engine/probe-schema-roots.py
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

INTERESTING = ["acc", "renew", "annuit", "seg", "mortgage", "polic", "fund",
               "invest", "asset", "product", "holding", "benefit", "gic"]


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


def try_shape(label: str, payload: dict) -> list:
    print(f"\n-- attempt: {label}")
    try:
        data = call(payload)
    except Exception as e:
        print(f"   transport error: {e}")
        return []
    if data.get("Code", 0) != 0:
        print(f"   rejected: Code={data.get('Code')} {json.dumps(data.get('Msg', ''))[:200]}")
        return []
    rows = data.get("Schema", {}).get("Data", []) or []
    print(f"   returned {len(rows)} schema rows")
    return rows


def main() -> None:
    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only). Load .env from the repo root.")

    rows = try_shape("full tree ($TREE /)", {
        "Schema": {"Scope": {"Fields": {"Key": 1, "Name": 1, "Type": 1, "Assignable": 1}},
                   "Criteria": {"SearchQuery": {"Key": {"$TREE": "/"}}}},
        "Compatibility": {"SchemaObject": "1.0"},
    })
    if not rows:
        rows = try_shape("no criteria (read all)", {
            "Schema": {"Scope": {"Fields": {"Key": 1, "Name": 1, "Type": 1, "Assignable": 1}}},
            "Compatibility": {"SchemaObject": "1.0"},
        })
    if not rows:
        print("\nBoth shapes rejected. Paste this output back; next step is the "
              "Maximizer API docs / support question, not more probing.")
        return

    roots = {}
    for r in rows:
        key = str(r.get("Key") or "")
        if not key.startswith("/"):
            continue
        root = "/" + key.split("/")[1] if len(key.split("/")) > 1 else key
        roots[root] = roots.get(root, 0) + 1

    print("\n" + "=" * 60)
    print(f"DISTINCT TOP-LEVEL OBJECTS ({len(roots)}):")
    print("=" * 60)
    for root in sorted(roots):
        flag = " <-- INTERESTING" if any(t in root.lower() for t in INTERESTING) else ""
        print(f"  {root}  ({roots[root]} fields){flag}")

    print("\nFields under interesting non-AbEntry roots:")
    shown = 0
    for r in rows:
        key = str(r.get("Key") or "")
        if key.startswith("/AbEntry"):
            continue
        low = key.lower()
        if any(t in low for t in ("renew", "annuit", "segregated", "mortgage",
                                  "gic", "expiry", "maturit")):
            print(f"  Key={key} | Name={r.get('Name')} | Type={r.get('Type')} "
                  f"| Assignable={r.get('Assignable')}")
            shown += 1
    if not shown:
        print("  (none)")

    print("\nProbe complete. READ-ONLY - nothing was changed.")
    print("Paste this whole output back to Claude.")


if __name__ == "__main__":
    main()
