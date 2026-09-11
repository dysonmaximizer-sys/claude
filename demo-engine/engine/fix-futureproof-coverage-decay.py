#!/usr/bin/env python3
"""Make the coverage-decay half of the Futureproof stage demo true, re-runnably.

Beat 1 asks which households have gone longest without contact. That answer is
driven by Date Last Contacted ($TYPEID(60059)); Days Since Last Contacted
($TYPEID(838)) is a FORMULA off it and must never be written.

This script is idempotent. Dates are always recomputed relative to the run date
(rule 7), so re-running after a rehearsal re-ages the three households without
duplicating anything. The back-dated calls are created once and then skipped,
guarded by manifests/futureproof/coverage-decay.json.

  set -a; source futureproof.env; set +a
  python3 engine/fix-futureproof-coverage-decay.py            # dry run
  python3 engine/fix-futureproof-coverage-decay.py --apply
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tenant_guard import assert_tenant  # noqa: E402

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
COMPAT = {"AbEntryKey": "2.0"}
PACIFIC = ZoneInfo("America/Vancouver")

KEYS_MANIFEST = "manifests/futureproof/abentry-keys.json"
MANIFEST = "manifests/futureproof/coverage-decay.json"

DLC = "Udf/$TYPEID(60059)"          # Date Last Contacted, writable
DAYS_SINCE = "Udf/$TYPEID(838)"     # formula, NEVER write
SEG = "Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)"
MASTER = "VXNlcglNQVNURVI="         # rule 10 owner, displays "Barb Smith"
PHONE_CALL = "60001"

AUDIT_MARKERS = ["changed from", "field changed", "modified", "changed to",
                 "hotlist task", "opportunity created", "date last contacted"]

# name -> (days back, call subject, duration minutes)
TARGETS = [
    ("Peter and Mary Cameron Family", 104, "Portfolio review call", 22),
    ("Hartfield Family",               97, "Semi-annual review call", 18),
    ("Vincent  Household",             91, "TFSA and account review call", 16),
]

# Households that had NO Date Last Contacted at all. A null sorts unpredictably
# and drops out of any recency answer, so give them real dates. Kept well inside
# 90 days so they never compete with the three decay targets above. Relative to
# the run date like everything else, so re-runs keep them fresh.
BACKFILL = [
    ("Michael and Jennifer Sorenson Family", 43),
    ("James and Margaret Dutton Family", 58),
]

TODAY = datetime.now(PACIFIC).date()


def call(endpoint: str, payload: dict) -> dict:
    for attempt in range(6):
        r = requests.post("%s/%s" % (BASE, endpoint),
                          headers={"Authorization": "Bearer %s" % PAT,
                                   "Content-Type": "application/json"},
                          json=payload, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 0)) or 10 * (attempt + 1))
            continue
        if r.status_code in (401, 403):
            sys.exit("AUTH FAILED (%s). Check futureproof.env." % r.status_code)
        r.raise_for_status()
        time.sleep(0.35)
        return r.json()
    raise RuntimeError("rate-limited after 6 tries on %s" % endpoint)


def one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def dt(days_ago: int, hm: str) -> str:
    """Intended-Pacific wall clock -> UTC string (rule 7b)."""
    day = TODAY - timedelta(days=days_ago)
    local = datetime(day.year, day.month, day.day,
                     int(hm[:2]), int(hm[3:5]), tzinfo=PACIFIC)
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def norm(s: str) -> str:
    return " ".join(str(s or "").split()).lower()


def created_key(data: dict, obj: str) -> Optional[str]:
    node = (data.get(obj) or {}).get("Data")
    if isinstance(node, list) and node:
        return node[0].get("Key")
    if isinstance(node, dict):
        return node.get("Key")
    return None


def read_individuals() -> list:
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "LastName": 1,
                                                         DLC: 1, DAYS_SINCE: 1, SEG: 1}},
                                    "Criteria": {"SearchQuery": {"Type": {"$EQ": "Individual"}}},
                                    "Options": {"Limit": 500}}, "Compatibility": COMPAT})
    rows = res.get("AbEntry", {}).get("Data") or []
    if not rows:
        sys.exit("0 Individuals returned. An unknown Scope field returns an empty set in "
                 "this API, so this is a broken read, not an empty book. Nothing written.")
    return rows


def resolve(name: str, keymap: dict, rows: list) -> Optional[str]:
    for rec in keymap.values():
        if norm(rec.get("name")) == norm(name):
            return rec.get("abentry_key")
    hits = [r for r in rows if norm(r.get("LastName")) == norm(name)]
    if len(hits) == 1:
        return hits[0]["Key"]
    if len(hits) > 1:
        print("  !! %r matches %d households, ambiguous - skipped" % (name, len(hits)))
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not PAT:
        sys.exit("No token. Run: set -a; source futureproof.env; set +a")

    print("== Futureproof coverage decay ==  run date %s (Pacific)" % TODAY)
    assert_tenant("futureproof", call)

    keymap = json.load(open(KEYS_MANIFEST)) if os.path.exists(KEYS_MANIFEST) else {}
    rows = read_individuals()

    plan = []
    for name, days, subject, mins in TARGETS:
        key = resolve(name, keymap, rows)
        if not key:
            sys.exit("Could not resolve %r. Nothing written." % name)
        src = "abentry-keys.json" if any(norm(v.get("name")) == norm(name)
                                         for v in keymap.values()) else "LastName read"
        date_str = (TODAY - timedelta(days=days)).isoformat()
        plan.append({"name": name, "key": key, "days": days, "date": date_str,
                     "subject": subject, "mins": mins, "src": src})
        print("  %-34s -> %s (%d days back)  [resolved via %s]" % (name, date_str, days, src))

    fill = []
    for name, days in BACKFILL:
        key = resolve(name, keymap, rows)
        if not key:
            sys.exit("Could not resolve backfill target %r. Nothing written." % name)
        date_str = (TODAY - timedelta(days=days)).isoformat()
        fill.append({"name": name, "key": key, "days": days, "date": date_str})
        print("  backfill %-25s -> %s (%d days back)" % (name, date_str, days))

    make_calls = not os.path.exists(MANIFEST)
    print("  back-dated calls: %s" % ("CREATE (no manifest yet)" if make_calls
                                      else "SKIP (%s exists)" % MANIFEST))

    if not args.apply:
        print("\nDRY RUN. Re-run with --apply to write.")
        return

    # ---- 1. Date Last Contacted
    print("\nwriting Date Last Contacted...")
    swept_scope = []
    for p in plan + fill:
        out = call("Update", {"AbEntry": {"Data": {"Key": p["key"], DLC: p["date"]}},
                              "Compatibility": COMPAT})
        print("  %-34s code %s" % (p["name"], out.get("Code")))
        swept_scope.append(p["key"])

    # ---- 2. back-dated phone calls, once
    manifest = {"story": "coverage-decay", "tenant": "futureproof",
                "created": [], "seeded": TODAY.isoformat()}
    if make_calls:
        print("\ncreating back-dated phone calls...")
        for p in plan:
            payload = {"Key": None, "Subject": p["subject"], "Description": p["subject"],
                       "Type": PHONE_CALL,
                       "StartDate": dt(p["days"], "10:00"),
                       "EndDate": dt(p["days"], "10:%02d" % p["mins"]),
                       "User": MASTER, "AbEntryKey": p["key"], "Direction": 2}
            data = call("Create", {"InteractionLog": {"Data": payload},
                                   "Compatibility": COMPAT})
            k = created_key(data, "InteractionLog")
            if not k:
                print("  CALL FAILED for %s: %s" % (p["name"], json.dumps(data)[:250]))
                continue
            print("  %-34s %s (%d min)" % (p["name"], p["subject"], p["mins"]))
            manifest["created"].append({"kind": "InteractionLog", "key": k,
                                        "label": "%s - %s" % (p["name"], p["subject"])})
        with open(MANIFEST, "w") as fh:
            json.dump(manifest, fh, indent=2)
        print("  manifest written: %s" % MANIFEST)
    else:
        print("\nskipping call creation, manifest already exists")

    # ---- 3. sweep audit notes from the last 10 minutes
    print("\nsweeping audit notes (last 10 minutes)...")
    cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=10)
    swept = kept = 0
    for p in plan + fill:
        res = call("Read", {"Note": {"Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
                                     "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": p["key"]}}},
                                     "Options": {"Limit": 300}}, "Compatibility": COMPAT})
        for note in res.get("Note", {}).get("Data") or []:
            raw = str(note.get("DateTime") or "")[:19]
            try:
                when = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
            except ValueError:
                continue
            if when < cutoff:
                continue
            text = str(note.get("Text") or "")
            if any(m in text.lower() for m in AUDIT_MARKERS):
                dres = call("Delete", {"Note": {"Data": {"Key": note["Key"]}},
                                       "Compatibility": COMPAT})
                if dres.get("Code", 0) == 0:
                    swept += 1
                else:
                    print("  ! delete failed on %s" % p["name"])
            else:
                kept += 1
                print("  ! recent non-audit note on %s left alone: %r" % (p["name"], text[:70]))
    print("  %d audit note(s) swept, %d recent note(s) kept" % (swept, kept))

    # ---- 4. verify
    print("\nverifying...")
    rows = read_individuals()
    by_key = {r["Key"]: r for r in rows}
    for p in plan + fill:
        r = by_key.get(p["key"], {})
        print("  %-34s dateLastContacted=%-12s daysSince=%-6s seg=%s" % (
            p["name"], one(r.get(DLC)) or "NONE", one(r.get(DAYS_SINCE)), one(r.get(SEG))))

    target_keys = {p["key"] for p in plan + fill}
    others = []
    for r in rows:
        if r["Key"] in target_keys:
            continue
        ds = one(r.get(DAYS_SINCE))
        try:
            if ds is not None and float(ds) >= 90:
                others.append((str(r.get("LastName")), float(ds)))
        except (TypeError, ValueError):
            continue
    if others:
        print("  !! %d OTHER household(s) at 90+ days:" % len(others))
        for n, ds in sorted(others, key=lambda x: -x[1]):
            print("       %-40s %.0f days" % (n, ds))
    else:
        print("  no other household is at 90+ days")

    a_tier = [str(r.get("LastName")) for r in rows if str(one(r.get(SEG))) == "1"]
    print("  A-tier households: %d" % len(a_tier))
    for p in plan:
        seg = str(one(by_key.get(p["key"], {}).get(SEG)))
        print("     %-34s %s" % (p["name"], "A" if seg == "1" else "NOT A (seg=%s)" % seg))


if __name__ == "__main__":
    main()
