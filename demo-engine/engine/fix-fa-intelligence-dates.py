#!/usr/bin/env python3
"""
Fix pass for update-fa-intelligence.py (2026-07-21): the first run spread
renewal dates over 8 months, pushing some into next calendar year, outside
the report's This Fiscal Year filter (tenant fiscal year = calendar year,
inferred from the KYC chart bucketing ending in December).

This re-dates every GIC Expiry and Group Benefits renewal the first run
touched to a spread that stays inside the current fiscal year (latest
~Dec 8). Uses the existing baseline file, so --restore on the main script
still puts everything back to the true originals.

Run:    python3 engine/fix-fa-intelligence-dates.py
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
GB_RENEWAL = "Udf/$TYPEID(1082)"

# In-fiscal-year spreads (fiscal year = calendar year; latest lands ~Dec 8
# when run in late July, and the cap below protects later runs too).
GIC_OFFSETS = [21, 45, 70, 105, 140]
GB_OFFSETS = [60, 130]

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


def fy_capped(offset_days: int) -> str:
    """Date offset from today, clamped to stay inside the current calendar
    (= fiscal) year with ~3 weeks of headroom."""
    fy_cap = datetime(TODAY.year, 12, 15)
    target = TODAY + timedelta(days=offset_days)
    if target > fy_cap:
        target = fy_cap
    return target.strftime("%Y-%m-%d")


def unlist(v):
    return v[0] if isinstance(v, list) and v else v


def main() -> None:
    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only). Load .env from the repo root.")
    if not os.path.exists(BASELINE):
        sys.exit(f"No baseline at {BASELINE} - run update-fa-intelligence.py first.")

    with open(BASELINE) as f:
        baseline = json.load(f)

    gic_changes = [c for c in baseline.get("changes", []) if c["field"] == GIC]
    gb_changes = [c for c in baseline.get("changes", []) if c["field"] == GB_RENEWAL]
    if not gic_changes and not gb_changes:
        sys.exit("Baseline has no GIC / Group Benefits changes - nothing to fix.")

    fails = 0
    touched = []

    print(f"Re-dating {len(gic_changes)} GIC expiry and {len(gb_changes)} "
          f"Group Benefits renewal date(s) into this fiscal year ...")
    for changes, offsets, field_name in ((gic_changes, GIC_OFFSETS, GIC),
                                         (gb_changes, GB_OFFSETS, GB_RENEWAL)):
        for ch, off in zip(changes, offsets):
            new_date = fy_capped(off)
            data = call("Update", {
                "AbEntry": {"Data": {"Key": ch["key"], field_name: new_date}},
                "Compatibility": {"AbEntryKey": "2.0"},
            })
            ok = data.get("Code", 0) == 0
            print(f"  {'+' if ok else '- FAILED:'} {ch['label']}: "
                  f"{str(ch['new'])[:10]} -> {new_date}")
            if not ok:
                print(f"      {json.dumps(data)[:300]}")
                fails += 1
                continue
            # read-back verify
            rb = call("Read", {
                "AbEntry": {"Scope": {"Fields": {"Key": 1, field_name: 1}},
                            "Criteria": {"SearchQuery": {"Key": {"$EQ": ch["key"]}}}},
                "Compatibility": {"AbEntryKey": "2.0"},
            })
            rows = rb.get("AbEntry", {}).get("Data", []) or []
            got = str(unlist(rows[0].get(field_name)) if rows else "")
            if not got.startswith(new_date):
                print(f"  ! read-back mismatch on {ch['label']}: got {got!r}")
                fails += 1
                continue
            ch["new"] = new_date  # keep the baseline's record accurate
            touched.append(ch["key"])

    print("\nSweeping audit notes ...")
    swept = 0
    today_str = TODAY.strftime("%Y-%m-%d")
    for pk in set(touched):
        data = call("Read", {"Note": {
            "Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
            "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": pk}}},
        }})
        for note in data.get("Note", {}).get("Data", []) or []:
            if not (note.get("DateTime") or "").startswith(today_str):
                continue
            if any(m in str(note.get("Text", "")) for m in AUDIT_MARKERS):
                d = call("Delete", {"Note": {"Data": {"Key": note["Key"]}}})
                if d.get("Code", 0) == 0:
                    swept += 1
    print(f"  swept {swept} audit note(s)")

    with open(BASELINE, "w") as f:
        json.dump(baseline, f, indent=2)

    if fails:
        print(f"\n{fails} change(s) FAILED - paste this whole output back.")
        sys.exit(1)
    print("\nDone: every renewal date now lands inside this fiscal year "
          "(latest ~Dec 8). Check the tiles after the next report data sync.")
    print("Undo everything (originals):  python3 engine/update-fa-intelligence.py --restore")


if __name__ == "__main__":
    main()
