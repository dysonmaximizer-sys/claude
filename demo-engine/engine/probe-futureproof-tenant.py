#!/usr/bin/env python3
"""READ-ONLY reconnaissance of the Futureproof demo tenant. Writes NOTHING.

Follows probe-bizplus-tenant.py, but targets only the facts the Futureproof
stage demo depends on and that the generic probe did not cover:
the Estate Planning folder, Date Last Contacted, the two FSE $TAG fields,
and whether the named households actually exist.

Run with the Futureproof env loaded:
  set -a; source futureproof.env; set +a
  python3 engine/probe-futureproof-tenant.py
"""

import json
import os
import sys
import time
from typing import Optional

import requests

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
COMPAT = {"AbEntryKey": "2.0"}


def call(endpoint: str, payload: dict) -> dict:
    for attempt in range(6):
        r = requests.post(f"{BASE}/{endpoint}",
                          headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                          json=payload, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 0)) or 10 * (attempt + 1))
            continue
        if r.status_code in (401, 403):
            sys.exit("AUTH FAILED (%s): token not accepted. Check futureproof.env "
                     "(wrong tenant? different base URL?)" % r.status_code)
        r.raise_for_status()
        time.sleep(0.35)
        return r.json()
    raise RuntimeError("rate-limited after 6 tries on %s" % endpoint)


def aliases(f: dict) -> str:
    return json.dumps(f.get("Alias") or [])


def main() -> None:
    if not PAT:
        sys.exit("No token. Load it with: set -a; source futureproof.env; set +a")

    print("== A. Pulling the AbEntry field catalog ==")
    res = call("Read", {"Schema": {"Scope": {"Fields": {"Key": 1, "Alias": 1, "Name": 1, "Assignable": 1}},
                                   "Criteria": {"SearchQuery": {"Key": {"$TREE": "/AbEntry"}}}},
               "Compatibility": {"SchemaObject": "1.0"}})
    fields = res.get("Schema", {}).get("Data", [])
    print("  %d AbEntry fields retrieved" % len(fields))

    print("\n== B. Estate Planning folder (the story Lewis owns) ==")
    ep = [f for f in fields if "Estate Planning\\" in aliases(f)]
    for f in sorted(ep, key=lambda x: aliases(x)):
        flag = "writable" if f.get("Assignable") else "READ-ONLY"
        print("  [%s] %s | %s" % (flag, f.get("Name"), aliases(f)[:150]))
    print("  -> %d Estate Planning fields" % len(ep))

    print("\n== C. Date Last Contacted (coverage-decay question depends on it) ==")
    dlc = [f for f in fields if "last contacted" in json.dumps(f).lower()]
    for f in dlc:
        flag = "writable" if f.get("Assignable") else "READ-ONLY (formula)"
        print("  [%s] %s | %s" % (flag, f.get("Name"), aliases(f)[:150]))
    if not dlc:
        print("  !! ABSENT - FSE addresses this as Udf/$TYPEID(60059). Not found here.")

    print("\n== D. Do FSE's two $TAG fields exist here? ==")
    for tag in ["WME_CLIENTINFO_SEGMENTATION", "WME_CLIENTINFO_REV_NEXTKYC"]:
        hit = [f for f in fields if tag in json.dumps(f)]
        print("  $TAG(%s): %s" % (tag, "FOUND -> " + aliases(hit[0])[:120] if hit else "ABSENT - address by $NAME instead"))
    any_tag = [f for f in fields if "$TAG(" in aliases(f)]
    print("  fields carrying any $TAG alias: %d" % len(any_tag))

    print("\n== E. Base (non-UDF) AbEntry fields - which one carries the name? ==")
    base = sorted({str(f.get("Key", "")).split("/")[-1] for f in fields
                   if "Udf" not in str(f.get("Key", ""))})
    print("  %d base fields:" % len(base))
    print("  " + ", ".join(base))

    print("\n== F. Named households / companies in the book ==")
    print("  NOTE: an unknown field in Scope returns 0 rows, NOT an error. Trying variants.")
    for scope in (["Company"], ["Display"], ["FormattedName"], ["CompanyName"], ["FirstName", "LastName"]):
        sc = {"Key": 1, "Type": 1}
        for s in scope:
            sc[s] = 1
        try:
            res = call("Read", {"AbEntry": {"Scope": {"Fields": sc},
                                            "Criteria": {"SearchQuery": {"Type": {"$EQ": "Company"}}},
                                            "Options": {"Limit": 500}}, "Compatibility": COMPAT})
            rows = res.get("AbEntry", {}).get("Data", [])
            print("  scope %-26s -> %d rows" % (json.dumps(scope), len(rows)))
            if rows:
                for r_ in sorted(rows, key=lambda x: json.dumps(x)):
                    label = " ".join(str(r_.get(s, "")) for s in scope).strip()
                    print("    %s | %s" % (label[:58].ljust(58), r_.get("Key")))
                break
        except Exception as e:
            print("  scope %-26s -> ERROR %s" % (json.dumps(scope), str(e)[:70]))

    print("\n== G. Any 'review' date field anywhere (is there an estate-review field?) ==")
    for f in fields:
        blob = json.dumps(f)
        if "review" in blob.lower():
            flag = "writable" if f.get("Assignable") else "READ-ONLY"
            print("  [%s] %s | %s" % (flag, f.get("Name"), aliases(f)[:130]))

    print("\nRECON COMPLETE - nothing was written.")


if __name__ == "__main__":
    main()
