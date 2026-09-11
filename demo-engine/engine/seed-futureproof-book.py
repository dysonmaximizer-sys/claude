#!/usr/bin/env python3
"""Part 1 of the Futureproof book build: create households + contacts from CSV.

Households are created as Type "Individual" with the name in LastName, NOT the
CLAUDE.md {"Type":"Household","CompanyName":...} shape. See
docs/futureproof-tenant.md - the CLAUDE.md shape produces Company-typed records
which the MCP connector's "households" query cannot see, and the stage demo runs
through that connector.

  set -a; source futureproof.env; set +a
  python3 engine/seed-futureproof-book.py --limit 3
"""

import argparse
import csv
import json
import os
import sys
import time
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tenant_guard import assert_tenant  # noqa: E402

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
COMPAT = {"AbEntryKey": "2.0"}

CSV_PATH = "stories/futureproof/futureproof-new-households.csv"
MANIFEST = "manifests/futureproof/build-the-book.json"

SEGMENTATION = "Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)"
NEXT_KYC = "Udf/$TAG(WME_CLIENTINFO_REV_NEXTKYC)"
RECORD_TYPE = r"Udf/$NAME(WM_Client Info\Record Type - Mandatory)"
DATE_LAST_CONTACTED = "Udf/$TYPEID(60059)"
BIRTHDATE = "Udf/$TYPEID(124)"


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


def created_key(data: dict) -> Optional[str]:
    node = (data.get("AbEntry") or {}).get("Data")
    if isinstance(node, list) and node:
        return node[0].get("Key")
    if isinstance(node, dict):
        return node.get("Key")
    return None


def save(manifest: dict) -> None:
    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=2)


def make_address(row: dict) -> dict:
    return {"City": row["city"], "StateProvince": row["province"],
            "Country": "Canada", "ZipCode": row["postal_code"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="process only the first N rows")
    args = ap.parse_args()

    if not PAT:
        sys.exit("No token. Run: set -a; source futureproof.env; set +a")

    print("== Futureproof book build, Part 1 ==")
    assert_tenant("futureproof", call)

    if os.path.exists(MANIFEST):
        existing = json.load(open(MANIFEST))
    else:
        existing = {"story": "build-the-book", "tenant": "futureproof", "created": {}}

    rows = list(csv.DictReader(open(CSV_PATH)))
    if args.limit:
        rows = rows[:args.limit]
    print("  processing %d row(s)\n" % len(rows))

    for row in rows:
        ref = row["ref"]
        if ref in existing["created"]:
            print("%s already in manifest, skipping" % ref)
            continue

        print("%s  %s" % (ref, row["household_name"]))
        data = call("Create", {"AbEntry": {"Data": {
            "Key": None, "Type": "Individual", "LastName": row["household_name"],
            "Address": make_address(row),
        }}, "Compatibility": COMPAT})
        hh = created_key(data)
        if not hh:
            print("  HOUSEHOLD CREATE FAILED: %s" % json.dumps(data)[:400])
            save(existing)
            sys.exit("stopping - nothing further written for %s" % ref)
        print("  household key %s" % hh)
        existing["created"][ref] = {"household": hh, "household_name": row["household_name"],
                                    "contacts": []}
        save(existing)

        upd = call("Update", {"AbEntry": {"Data": {
            "Key": hh,
            SEGMENTATION: row["segmentation"],
            RECORD_TYPE: row["record_type"],
            NEXT_KYC: row["next_kyc_review"],
            DATE_LAST_CONTACTED: row["date_last_contacted"],
        }}, "Compatibility": COMPAT})
        print("  udf update code %s" % upd.get("Code"))

        for n in ("1", "2"):
            first = row["contact%s_first" % n].strip()
            if not first:
                continue
            payload = {"Key": None, "Type": "Contact", "ParentKey": hh,
                       "FirstName": first, "LastName": row["contact%s_last" % n].strip(),
                       "Email": {"Address": row["contact%s_email" % n].strip()},
                       "Phone1": {"Number": row["contact%s_phone" % n].strip()},
                       BIRTHDATE: row["contact%s_birthdate" % n].strip(),
                       "Address": make_address(row)}
            cdata = call("Create", {"AbEntry": {"Data": payload}, "Compatibility": COMPAT})
            ckey = created_key(cdata)
            if not ckey:
                print("  CONTACT %s FAILED: %s" % (n, json.dumps(cdata)[:300]))
                continue
            print("  contact %s (%s) key %s" % (n, first, ckey))
            existing["created"][ref]["contacts"].append(
                {"key": ckey, "name": "%s %s" % (first, row["contact%s_last" % n].strip())})
            save(existing)
        print("")

    print("Done. Manifest: %s" % MANIFEST)


if __name__ == "__main__":
    main()
