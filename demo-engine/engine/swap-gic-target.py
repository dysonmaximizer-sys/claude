#!/usr/bin/env python3
"""
Swap the fifth GIC Expiry target off Bill Graham (2026-07-21).

Bill Graham accepts AbEntry updates with Code 0 but the values read back
null (suspected May-2026 wizard-test orphan; now recorded in CLAUDE.md).
This picks the next clean supporting cast member, gives them the fifth
GIC expiry date (~Dec 8, inside the fiscal year), verifies with TWO
read-backs (partial reads lie on this tenant), and updates the baseline
so --restore stays accurate. Bill Graham is left alone.

Run:    python3 engine/swap-gic-target.py
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifests",
                        "fa-intelligence-baseline.json")

TODAY = datetime.now()
PACE = 0.35
GIC = "Udf/$TYPEID(575)"

# story cast + protected + known/suspected broken records
EXCLUDE_NAMES = ("sokolov", "renaud", "okafor", "whitfield", "bianchi",
                 "grewal", "fortin", "bill graham", "jameson thomas",
                 "lou cameron")

AUDIT_MARKERS = ("Hotlist Task Created", "Hotlist Task Modified", "Opportunity created",
                 "changed from", "Changed from")


def call(endpoint: str, payload: dict) -> dict:
    time.sleep(PACE)
    r = requests.post(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    if r.status_code == 429:
        wait = int(r.headers.get("Retry-After", "5"))
        print(f"  .. rate limited, waiting {wait}s")
        time.sleep(wait)
        return call(endpoint, payload)
    r.raise_for_status()
    return r.json()


def unlist(v):
    return v[0] if isinstance(v, list) and v else v


def display_name(row: dict) -> str:
    first, last = row.get("FirstName") or "", row.get("LastName") or ""
    if first or last:
        return f"{first} {last}".strip()
    return row.get("CompanyName") or "?"


def read_gic(key: str):
    data = call("Read", {
        "AbEntry": {"Scope": {"Fields": {"Key": 1, GIC: 1}},
                    "Criteria": {"SearchQuery": {"Key": {"$EQ": key}}}},
        "Compatibility": {"AbEntryKey": "2.0"},
    })
    rows = data.get("AbEntry", {}).get("Data", []) or []
    return unlist(rows[0].get(GIC)) if rows else None


def main() -> None:
    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only). Load .env from the repo root.")
    if not os.path.exists(BASELINE):
        sys.exit(f"No baseline at {BASELINE} - run update-fa-intelligence.py first.")
    with open(BASELINE) as f:
        baseline = json.load(f)

    taken = {c["key"] for c in baseline.get("changes", [])}

    print("1) Finding a clean replacement target ...")
    data = call("Read", {
        "AbEntry": {
            "Scope": {"Fields": {"Key": 1, "FirstName": 1, "LastName": 1,
                                 "CompanyName": 1, GIC: 1}},
            "Criteria": {"SearchQuery": {"Type": {"$EQ": "Household"}}},
            "OptionArgs": {"Limit": 500},
        },
        "Compatibility": {"AbEntryKey": "2.0"},
    })
    rows = data.get("AbEntry", {}).get("Data", []) or []
    seen, pool = set(), []
    for r in rows:
        k = r.get("Key")
        if not k or k in seen:
            continue
        seen.add(k)
        name = display_name(r).lower()
        is_person = bool(r.get("FirstName") or r.get("LastName"))
        if (is_person and k not in taken and not unlist(r.get(GIC))
                and name and not any(x in name for x in EXCLUDE_NAMES)):
            pool.append(r)
    pool.sort(key=display_name)
    if not pool:
        sys.exit("No eligible replacement found - paste this back.")
    target = pool[0]
    name = display_name(target)
    print(f"  replacement: {name}")

    # fifth GIC slot: ~Dec 8 this fiscal year
    fy_cap = datetime(TODAY.year, 12, 15)
    t = TODAY + timedelta(days=140)
    date = min(t, fy_cap).strftime("%Y-%m-%d")

    print(f"2) Setting GIC expiry {date} on {name} ...")
    res = call("Update", {
        "AbEntry": {"Data": {"Key": target["Key"], GIC: date}},
        "Compatibility": {"AbEntryKey": "2.0"},
    })
    if res.get("Code", 0) != 0:
        sys.exit(f"Update rejected: {json.dumps(res)[:300]} - paste this back.")

    print("3) Verifying (two read-backs; partial reads lie) ...")
    ok = False
    for attempt in (1, 2):
        got = str(read_gic(target["Key"]) or "")
        if got.startswith(date):
            print(f"  verified on read {attempt}: {got[:10]}")
            ok = True
            break
        print(f"  read {attempt}: {got!r}")
    if not ok:
        sys.exit(f"{name} also fails read-back - do NOT keep swapping; paste this back.")

    # baseline: mark Graham's entry dead, add the replacement
    for c in baseline["changes"]:
        if "graham" in (c.get("label") or "").lower() and c["field"] == GIC:
            c["suspect_orphan"] = True
            c["note"] = "write returned Code 0 but never stored; do not restore"
    baseline["changes"].append({"key": target["Key"], "field": GIC,
                                "old": unlist(target.get(GIC)), "new": date,
                                "label": name})
    with open(BASELINE, "w") as f:
        json.dump(baseline, f, indent=2)

    print("4) Sweeping audit notes ...")
    swept = 0
    today_str = TODAY.strftime("%Y-%m-%d")
    nd = call("Read", {"Note": {
        "Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
        "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": target["Key"]}}},
    }})
    for note in nd.get("Note", {}).get("Data", []) or []:
        if not (note.get("DateTime") or "").startswith(today_str):
            continue
        if any(m in str(note.get("Text", "")) for m in AUDIT_MARKERS):
            d = call("Delete", {"Note": {"Data": {"Key": note["Key"]}}})
            if d.get("Code", 0) == 0:
                swept += 1
    print(f"  swept {swept} audit note(s)")

    print(f"\nDone: fifth GIC expiry now lives on {name} ({date}), verified.")
    print("Bill Graham untouched and marked dead in the baseline.")


if __name__ == "__main__":
    main()
