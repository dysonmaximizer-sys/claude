#!/usr/bin/env python3
"""Demote the six unplanned A clients in the Futureproof book from 1 to 2.

Selection is by CURRENT VALUE, not by name: every Individual currently at
Segmentation 1, minus Hartfield Family (an intended A client) and minus the
households this build created. That handles the duplicate "Smith Household"
correctly, since only one of the two is at 1.

  set -a; source futureproof.env; set +a
  python3 engine/fix-futureproof-segmentation.py            # dry run
  python3 engine/fix-futureproof-segmentation.py --apply
"""
import json, os, sys, time
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tenant_guard import assert_tenant  # noqa: E402

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
COMPAT = {"AbEntryKey": "2.0"}
SEG = "Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)"
MANIFEST = "manifests/futureproof/build-the-book.json"

KEEP_AS_A = {"Hartfield Family"}
EXPECTED = {
    "Cameron Family",
    "Smith, Celine and Pete",
    "Smith Household",
    "Robertson Household",
    "Harris",
    "James and Margaret Dutton Family",
}


def call(endpoint, payload):
    for attempt in range(6):
        r = requests.post("%s/%s" % (BASE, endpoint),
                          headers={"Authorization": "Bearer %s" % PAT,
                                   "Content-Type": "application/json"},
                          json=payload, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 0)) or 10 * (attempt + 1)); continue
        if r.status_code in (401, 403):
            sys.exit("AUTH FAILED (%s)" % r.status_code)
        r.raise_for_status(); time.sleep(0.35); return r.json()
    raise RuntimeError("rate limited")


def one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def main():
    apply = "--apply" in sys.argv
    if not PAT:
        sys.exit("No token. set -a; source futureproof.env; set +a")
    assert_tenant("futureproof", call)

    built = set()
    if os.path.exists(MANIFEST):
        built = {r["household"] for r in json.load(open(MANIFEST))["created"].values()}
        # manifest keys are Individual-prefixed; compare on the record id body
        built = {k.split("\t")[-2] if "\t" in k else k for k in built}

    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "LastName": 1, SEG: 1}},
                                    "Criteria": {"SearchQuery": {"Type": {"$EQ": "Individual"}}},
                                    "Options": {"Limit": 500}}, "Compatibility": COMPAT})
    rows = res.get("AbEntry", {}).get("Data") or []
    if not rows:
        sys.exit("0 Individuals returned. Refusing to act.")

    a_clients = [r for r in rows if str(one(r.get(SEG))) == "1"]
    targets = [r for r in a_clients
               if str(r.get("LastName")) not in KEEP_AS_A
               and str(r.get("LastName")) not in
               {v["household_name"] for v in json.load(open(MANIFEST))["created"].values()}]

    print("  %d Individuals, %d currently at Segmentation 1" % (len(rows), len(a_clients)))
    print("  %d selected for demotion to 2:" % len(targets))
    for t in targets:
        print("    - %s" % t.get("LastName"))

    names = {str(t.get("LastName")) for t in targets}
    if names != EXPECTED or len(targets) != 6:
        sys.exit("SELECTION MISMATCH - nothing written.\n  expected: %s\n  got:      %s"
                 % (sorted(EXPECTED), sorted(names)))
    print("  selection matches the expected six exactly.")

    if not apply:
        print("\nDRY RUN. Re-run with --apply to write.")
        return

    print("\napplying...")
    for t in targets:
        out = call("Update", {"AbEntry": {"Data": {"Key": t["Key"], SEG: "2"}},
                              "Compatibility": COMPAT})
        print("  %-40s code %s" % (t.get("LastName"), out.get("Code")))

    print("\nreading back...")
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "LastName": 1, SEG: 1}},
                                    "Criteria": {"SearchQuery": {"Type": {"$EQ": "Individual"}}},
                                    "Options": {"Limit": 500}}, "Compatibility": COMPAT})
    after = res.get("AbEntry", {}).get("Data") or []
    still_a = sorted(str(r.get("LastName")) for r in after if str(one(r.get(SEG))) == "1")
    print("  Segmentation 1 after the run (%d):" % len(still_a))
    for n in still_a:
        print("    - %s" % n)
    for t in targets:
        now = [r for r in after if r.get("Key") == t["Key"]]
        val = one(now[0].get(SEG)) if now else "?"
        if str(val) != "2":
            print("  !! %s did not store, reads back %s" % (t.get("LastName"), val))


if __name__ == "__main__":
    main()
