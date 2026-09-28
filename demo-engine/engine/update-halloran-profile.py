#!/usr/bin/env python3
"""Fill in the Halloran profile fields so the record looks lived-in on screen.

Balance sheet and relationship fields on the household; employment, family,
estate, goals and risk profile on Dan, Priya and Maya. Values fit the Continuum
webinar script and the story anchors: Toronto family, Muskoka cottage bought
1999 (~$780k), RESP $91,400, Maya in Grade 12 (born Jan 2009, starts
university fall 2027), next review ~3 weeks after the Oct 1 webinar. Nothing
here mentions McGill or a cottage SALE: those land live and via Priya's June
call, so IQ Boost keeps citing the right sources.

All values are fictional. Prior values go to manifests/halloran-profile-<date>.json
so the run can be reversed. Every write is read back.

Usage (repo root):
  set -a; source .env; set +a
  python3 engine/update-halloran-profile.py            # write
  python3 engine/update-halloran-profile.py --dry-run  # show plan only
"""

import argparse
import json
import os
import sys
import time
from datetime import date

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
COMPAT = {"AbEntryKey": "2.0"}
HERE = os.path.dirname(os.path.abspath(__file__))
STORY = os.path.join(HERE, "..", "manifests", "webinar-mcgill-catch-manifest.json")
PRIORS = os.path.join(HERE, "..", "manifests", f"halloran-profile-{date.today().isoformat()}.json")


def U(n: int) -> str:
    return f"Udf/$TYPEID({n})"


YES, NO = "2", "1"
CANADA, ENGLISH, MARRIED, SINGLE = "1", "1", "1", "2"
MEDIUM, GOOD = "3", "2"

HOUSEHOLD = {
    U(29): 1650000,    # Home (Market Value)
    U(45): 780000,     # Cottage (Muskoka, bought 1999)
    U(33): 640000,     # RSP
    U(36): 176000,     # TFSA
    U(432): 310000,    # Non registered
    U(31): 14200,      # Cash-Chequing Acct
    U(32): 38500,      # Savings Acct
    U(50): 285000,     # Liabilities: Principle residence (mortgage)
    U(160): 1270100,   # Total Liquid Assets (incl. RESP 91,400)
    U(159): 2430000,   # Total Fixed Assets
    U(158): 285000,    # Total Liabilities
    U(228): "2011-05-16",  # Client Since
    U(113): "Tom and Grace Whitfield",  # Referred by (29-char max)
    U(114): YES,       # Met face to face
    U(115): "15 years",
    U(843): "2025-10-15",  # Last KYC Review (Next KYC stays 2026-10-15)
    U(5): "2026-11-19",    # Next Financial Plan Review
    U(356): YES,       # Wills
    U(358): YES,       # Life Insurance
    U(207): "Dan and Priya, married 1998. Daughter Maya (17), in Grade 12.",
    U(208): "Family cottage in Muskoka since 1999.",
}

SHARED_ADULT = {
    # person-level only: these write Code 0 on a household but store nothing
    U(1120): "2026-10-22",  # Next Portfolio Review: ~3 weeks after the webinar
    U(1014): "5",      # Goal: education fund
    U(1021): "5",      # Goal: retirement plan
    U(1019): "4",      # Goal: reduce taxable income
    U(1020): "3",      # Goal: maximize growth
    U(1032): "Paying for Maya's university without setting back retirement. "
             "Keeping taxes down as assets change hands.",
    U(1041): "Maya's university costs from fall 2027.",
    U(128): MARRIED, U(129): 1, U(126): CANADA, U(127): CANADA, U(511): ENGLISH,
    U(226): "1998-07-11",   # Anniversary Date
    U(816): MEDIUM, U(817): GOOD,
    U(952): YES, U(953): "2019-03-12",
    U(954): "Maya turns 18 in January 2027.",
    U(956): YES, U(965): YES, U(970): YES,
}

DAN = dict(SHARED_ADULT, **{
    "Position": "Director of Operations",
    U(119): "Director of Operations", U(120): "Operations executive",
    U(121): "Norrow Freight Ltd.",
    U(13): 185000, U(944): 205000,
    U(222): "Priya Halloran", U(227): "2032-06-30",
    U(211): "Cycling. Coached Maya's youth soccer team for six seasons.",
    U(802): 20, U(803): 70, U(804): 10,   # objectives: income / growth / aggressive
    U(807): 20, U(808): 60, U(809): 20,   # risk: low / medium / high
})

PRIYA = dict(SHARED_ADULT, **{
    "Position": "Pharmacist-Owner",
    U(119): "Pharmacist-Owner", U(120): "Pharmacist",
    U(121): "Glenview Pharmacy",
    U(13): 142000, U(944): 160000,
    U(222): "Dan Halloran", U(227): "2034-06-30",
    U(211): "Pottery. Board member, neighbourhood library foundation.",
    U(802): 25, U(803): 65, U(804): 10,
    U(807): 25, U(808): 60, U(809): 15,
})

MAYA = {
    U(128): SINGLE, U(126): CANADA, U(127): CANADA, U(511): ENGLISH,
    U(120): "Student",
    U(142): "Grade 12 (grad. June 2027)",  # 29-char max
    U(211): "Plays cello in the school orchestra. Varsity soccer.",
}

PLAN = [("Halloran Family", HOUSEHOLD), ("Dan Halloran", DAN),
        ("Priya Halloran", PRIYA), ("Maya Halloran", MAYA)]


def call(endpoint: str, payload: dict) -> dict:
    time.sleep(0.4)  # 429 pacing per CLAUDE.md
    r = requests.post(f"{BASE}/{endpoint}",
                      headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                      json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("Code") == -2:
        sys.exit("API auth failed - the PAT has likely expired: renew it in .env and rerun.")
    return data


def read(key: str, fields: list) -> dict:
    data = call("Read", {"AbEntry": {"Scope": {"Fields": {f: 1 for f in ["Key"] + fields}},
                                     "Criteria": {"SearchQuery": {"Key": {"$EQ": key}}}},
                         "Compatibility": COMPAT})
    rows = data.get("AbEntry", {}).get("Data", [])
    return rows[0] if rows else {}


def same(got, want) -> bool:
    if isinstance(got, list):
        got = got[0] if got else None
    if got is None:
        return False
    if isinstance(want, (int, float)):
        try:
            return float(got) == float(want)
        except (TypeError, ValueError):
            return False
    return str(got).startswith(str(want))


def notes(key: str) -> dict:
    data = call("Read", {"Note": {"Scope": {"Fields": {"Key": 1, "Text": 1}},
                                  "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": key}}}},
                         "Compatibility": COMPAT})
    return {n["Key"]: n for n in data.get("Note", {}).get("Data", []) or []}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not PAT:
        sys.exit("MAXIMIZER_PAT not set - run: set -a; source .env; set +a")
    with open(STORY) as f:
        story = json.load(f)
    keys = {r["label"].split(" (")[0]: r["key"] for r in story["records"] if r["kind"] == "AbEntry"}

    priors, problems, not_stored = {}, [], []
    note_before = {k: set(notes(k)) for k in keys.values()}
    for name, fields in PLAN:
        key = keys[name]
        prior = read(key, list(fields))
        priors[name] = {"key": key, "prior": {f: prior.get(f) for f in fields}}
        overwrite = [f for f in fields if prior.get(f) not in (None, [], "") and not same(prior.get(f), fields[f])]
        print(f"{name}: {len(fields)} fields"
              + (f" (overwriting {len(overwrite)} existing: {overwrite})" if overwrite else ""))
        if args.dry_run:
            continue
        res = call("Update", {"AbEntry": {"Data": dict({"Key": key}, **fields)}, "Compatibility": COMPAT})
        if res.get("Code", 0) != 0:
            # find the offending field(s) one at a time rather than guessing
            for f, v in fields.items():
                one = call("Update", {"AbEntry": {"Data": {"Key": key, f: v}}, "Compatibility": COMPAT})
                if one.get("Code", 0) != 0:
                    problems.append(f"{name} {f}={v!r}: {json.dumps(one.get('Msg'))[:160]}")
        back = read(key, list(fields))
        for f, v in fields.items():
            if not same(back.get(f), v) and not any(p.startswith(f"{name} {f}=") for p in problems):
                not_stored.append(f"{name} {f} (wanted {v!r}, read {back.get(f)!r})")

    if args.dry_run:
        print("\nDRY RUN - nothing written.")
        return
    with open(PRIORS, "w") as f:
        json.dump({"action": "halloran-profile", "date": date.today().isoformat(), "records": priors}, f, indent=2)

    swept = 0
    for k, before in note_before.items():
        for nk, n in notes(k).items():
            if nk in before:
                continue
            t = (n.get("Text") or "").lower()
            if any(m in t for m in ["changed from", "changed to", "modified", "field changed"]):
                swept += call("Delete", {"Note": {"Data": {"Key": nk}}, "Compatibility": COMPAT}).get("Code", 0) == 0
            else:
                print(f"  ! unexpected new note left alone: {(n.get('Text') or '')[:80]!r}")

    print(f"\nPrior values saved to {os.path.basename(PRIORS)}. Audit notes swept: {swept}.")
    if problems:
        print("REJECTED by the API:\n  - " + "\n  - ".join(problems))
    if not_stored:
        print("ACCEPTED BUT NOT STORED (read back empty or different):\n  - " + "\n  - ".join(not_stored))
    if not problems and not not_stored:
        print("All fields written and verified by read-back.")


if __name__ == "__main__":
    main()
