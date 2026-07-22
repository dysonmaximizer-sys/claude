#!/usr/bin/env python3
"""
FA Intelligence realism pass — supporting cast only.

Makes the Upcoming Reviews reporting page look lived-in using fields the
2026-07-21 probe validated (see CLAUDE.md):

  1. GIC Expiry Date (Udf/$TYPEID 575) on FIVE supporting cast entries,
     spread over the next 8 months, so the GIC tile stops reading zero.
  2. Group Benefits renewal date (Udf/$TYPEID 1082) on up to TWO Company
     entries, so the Group Benefits tile has a chance to populate (the
     tile's exact source is unconfirmed; eyeball after running).
  3. Next KYC Review nudged for TWO supporting entries into the thin
     months (~Aug and ~Nov) so the Upcoming KYC chart loses its gaps.

Deliberately untouched: Managed Segregated Funds, Managed Mortgages,
Annuities (no writable fields exist - FSE Accounts module, not exposed
via API), main story players (Sokolov, Renaud, Okafor story cast), and
all birthdates.

Every original value is saved to manifests/fa-intelligence-baseline.json
before writing. Undo everything with --restore.

Run:    python3 engine/update-fa-intelligence.py
        python3 engine/update-fa-intelligence.py --restore
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

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
NEXTKYC = "Udf/$TAG(WME_CLIENTINFO_REV_NEXTKYC)"

# Never touch: engine-protected cast + story households (all manifest-owned).
EXCLUDE_NAMES = ("sokolov", "renaud", "okafor", "whitfield", "bianchi",
                 "grewal", "fortin")

AUDIT_MARKERS = ("Hotlist Task Created", "Hotlist Task Modified", "Opportunity created",
                 "changed from", "Changed from")


def call(endpoint: str, payload: dict, quiet: bool = False) -> dict:
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
        return call(endpoint, payload, quiet)
    r.raise_for_status()
    data = r.json()
    if data.get("Code", 0) != 0 and not quiet:
        print(f"  !! Code={data.get('Code')} on {endpoint}: {json.dumps(data)[:400]}")
    return data


def unlist(v):
    return v[0] if isinstance(v, list) and v else v


def display_name(row: dict) -> str:
    first, last = row.get("FirstName") or "", row.get("LastName") or ""
    if first or last:
        return f"{first} {last}".strip()
    return row.get("CompanyName") or "?"


def read_book() -> list:
    """Type=Household returns ALL entries on this tenant (validated quirk);
    dedupe by key."""
    data = call("Read", {
        "AbEntry": {
            "Scope": {"Fields": {"Key": 1, "Type": 1, "FirstName": 1, "LastName": 1,
                                 "CompanyName": 1, GIC: 1, GB_RENEWAL: 1, NEXTKYC: 1}},
            "Criteria": {"SearchQuery": {"Type": {"$EQ": "Household"}}},
            "OptionArgs": {"Limit": 500},
        },
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    rows = data.get("AbEntry", {}).get("Data", []) or []
    seen, out = set(), []
    for r in rows:
        k = r.get("Key")
        if k and k not in seen:
            seen.add(k)
            out.append(r)
    return out


def eligible(row: dict) -> bool:
    name = (display_name(row) or "").lower()
    return bool(name) and not any(x in name for x in EXCLUDE_NAMES)


def is_company(row: dict) -> bool:
    name = (row.get("CompanyName") or "").lower()
    return bool(name) and not row.get("FirstName") and not row.get("LastName") \
        and "family" not in name and "household" not in name


def upd(key: str, field: str, value, label: str, what: str,
        baseline: dict, old_value) -> bool:
    baseline["changes"].append({"key": key, "field": field,
                                "old": old_value, "new": value, "label": label})
    data = call("Update", {
        "AbEntry": {"Data": {"Key": key, field: value}},
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    ok = data.get("Code", 0) == 0
    print(f"  {'+' if ok else '- FAILED:'} {label}: {what}")
    if not ok:
        print(f"      {json.dumps(data)[:300]}")
    return ok


def verify(key: str, field: str, want: str, label: str) -> bool:
    data = call("Read", {
        "AbEntry": {"Scope": {"Fields": {"Key": 1, field: 1}},
                    "Criteria": {"SearchQuery": {"Key": {"$EQ": key}}}},
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    rows = data.get("AbEntry", {}).get("Data", []) or []
    got = str(unlist(rows[0].get(field)) if rows else "")
    ok = got.startswith(want[:10])
    if not ok:
        print(f"  ! read-back mismatch on {label}: got {got!r}, wanted {want!r}")
    return ok


def sweep_audit_notes(parent_keys: list) -> None:
    swept = 0
    for pk in parent_keys:
        data = call("Read", {"Note": {
            "Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
            "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": pk}}},
        }}, quiet=True)
        today_str = TODAY.strftime("%Y-%m-%d")
        for note in data.get("Note", {}).get("Data", []) or []:
            text = str(note.get("Text", ""))
            if not (note.get("DateTime") or "").startswith(today_str):
                continue
            if any(m in text for m in AUDIT_MARKERS):
                d = call("Delete", {"Note": {"Data": {"Key": note["Key"]}}}, quiet=True)
                if d.get("Code", 0) == 0:
                    swept += 1
    print(f"  swept {swept} audit note(s)")


def restore() -> None:
    if not os.path.exists(BASELINE):
        sys.exit(f"No baseline at {BASELINE} - nothing to restore.")
    with open(BASELINE) as f:
        baseline = json.load(f)
    fails = 0
    for ch in reversed(baseline.get("changes", [])):
        old = ch["old"] if ch["old"] not in ("", []) else None
        data = call("Update", {
            "AbEntry": {"Data": {"Key": ch["key"], ch["field"]: old}},
            "Compatibility": {"AbEntryKey": "2.0"},
        }, quiet=True)
        ok = data.get("Code", 0) == 0
        print(f"  {'restored' if ok else 'FAILED restore'}: {ch['label']} ({ch['field']})")
        if not ok:
            fails += 1
    sweep_audit_notes(list({ch["key"] for ch in baseline.get("changes", [])}))
    if fails == 0:
        os.remove(BASELINE)
        print("Baseline removed - tenant back to pre-run state.")
    else:
        print(f"{fails} restore(s) failed - baseline kept; paste this output back.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only). Load .env from the repo root.")

    if args.restore:
        restore()
        return

    if os.path.exists(BASELINE):
        sys.exit(f"Baseline already exists ({BASELINE}). Run --restore first, "
                 "or delete it if the last run was already eyeballed and kept.")

    print("1) Reading the book ...")
    book = read_book()
    print(f"  {len(book)} entries")
    if len(book) > 150:
        sys.exit("Unexpected volume (>150 entries) - STOPPING per safety rule 1. "
                 "Is this really the demo tenant?")

    pool = sorted([r for r in book if eligible(r)], key=display_name)
    baseline = {"created": TODAY.isoformat(), "changes": []}
    touched = []

    # ---- 2. GIC Expiry Date on five supporting individuals/households
    print("\n2) GIC Expiry Date (tile: GIC - GIC Expiry Date) ...")
    gic_targets = [r for r in pool if not unlist(r.get(GIC)) and not is_company(r)][:5]
    # Stay inside the current fiscal year (= calendar year on this tenant,
    # learned 2026-07-21): the report's This Fiscal Year filter drops
    # anything landing after December.
    gic_offsets = [21, 45, 70, 105, 140]
    for row, off in zip(gic_targets, gic_offsets):
        date = (TODAY + timedelta(days=off)).strftime("%Y-%m-%d")
        if upd(row["Key"], GIC, date, display_name(row), f"GIC expiry {date}",
               baseline, unlist(row.get(GIC))):
            verify(row["Key"], GIC, date, display_name(row))
            touched.append(row["Key"])

    # ---- 3. Group Benefits renewal on up to two Company entries
    print("\n3) Group Benefits renewal date (tile: Group Benefits) ...")
    companies = [r for r in pool if is_company(r)][:2]
    if not companies:
        print("  no company entries in the supporting cast - tile stays zero, tell Claude")
    gb_offsets = [60, 130]  # in-fiscal-year (see note above)
    for row, off in zip(companies, gb_offsets):
        date = (TODAY + timedelta(days=off)).strftime("%Y-%m-%d")
        if upd(row["Key"], GB_RENEWAL, date, display_name(row), f"GB renewal {date}",
               baseline, unlist(row.get(GB_RENEWAL))):
            verify(row["Key"], GB_RENEWAL, date, display_name(row))
            touched.append(row["Key"])

    # ---- 4. pad the thin KYC months (~Aug and ~Nov on the current chart)
    print("\n4) Nudging two Next KYC Reviews into the thin months ...")
    kyc_pool = []
    for r in pool:
        if r["Key"] in touched or is_company(r):
            continue
        v = unlist(r.get(NEXTKYC))
        if not v:
            continue
        try:
            dt = datetime.strptime(str(v)[:10], "%Y-%m-%d")
        except ValueError:
            continue
        if (dt - TODAY).days > 150:  # far-out reviews: moving them costs nothing visible
            kyc_pool.append((r, str(v)[:10]))
    for (row, old), off in zip(kyc_pool[:2], [25, 115]):  # ~4 wks out, ~4 mos out
        date = (TODAY + timedelta(days=off)).strftime("%Y-%m-%d")
        if upd(row["Key"], NEXTKYC, date, display_name(row),
               f"Next KYC {old} -> {date}", baseline, old):
            verify(row["Key"], NEXTKYC, date, display_name(row))
            touched.append(row["Key"])

    # ---- 5. save baseline, sweep, report
    with open(BASELINE, "w") as f:
        json.dump(baseline, f, indent=2)

    print("\n5) Sweeping audit notes ...")
    sweep_audit_notes(list(set(touched)))

    print(f"\nDone: {len(baseline['changes'])} field changes, baseline saved for --restore.")
    print("\nEyeball checklist (FA Intelligence > Upcoming Reviews, after next data sync):")
    print("  - GIC tile shows a number (data sync may take until the next report refresh)")
    print("  - Group Benefits tile: if still 0, the tile reads something else - tell Claude")
    print("  - Upcoming KYC chart: the two thin months now show at least 2 each")
    print("  - Seg Funds / Mortgages / Annuities tiles STAY 0 (no writable source; honest)")
    print("  - spot-check one changed client: no same-day audit notes on their record")
    print(f"\nUndo everything:  python3 engine/update-fa-intelligence.py --restore")


if __name__ == "__main__":
    main()
