#!/usr/bin/env python3
"""Part 2 of the Futureproof book build: renames, segmentation, addresses.

  set -a; source futureproof.env; set +a
  python3 engine/fix-futureproof-part2.py            # dry run
  python3 engine/fix-futureproof-part2.py --apply

Selection is by exact LastName. Any target that is missing, duplicated, or
already renamed aborts the whole run before a single write.

IMPORTANT: renaming "Michael and Jennifer Cameron Family" removes one of the two
names tenant_guard.py fingerprints on. The guard must be repointed at
"James and Margaret Dutton Family" in the same change or every later seeder
loses its safety net. This script refuses to run until that edit is in place.
"""
import json, os, sys, time
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tenant_guard import assert_tenant, FINGERPRINTS  # noqa: E402

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
COMPAT = {"AbEntryKey": "2.0"}
SEG = "Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)"
CHILDREN = "Udf/$TYPEID(549)"
MANIFEST = "manifests/futureproof/build-the-book.json"

RENAMES = {
    "Cameron Family": "Lou and Nancy Whitfield Family",
    "Michael and Jennifer Cameron Family": "Michael and Jennifer Sorenson Family",
}
CONTACT_SURNAME = {"Cameron Family": "Whitfield",
                   "Michael and Jennifer Cameron Family": "Sorenson"}
PROMOTE_TO_A = ["Peter and Mary Cameron Family", "Vincent  Household"]  # note double space
ADDRESSES = {
    "Lewis Household":                     ("Ottawa",  "ON", "K1P 5G4"),
    "Harris":                              ("Ottawa",  "ON", "K1P 1J9"),
    "Jones Family":                        ("Kamloops","BC", "V2C 5N3"),
    "Myles, Rick and Melissa":             ("Canmore", "AB", "T1W 2T8"),
    "Thomas Household":                    ("Regina",  "SK", "S4P 3Y2"),
    # Displays as "Thomas, Jameson - Thomas Household" but that is a composite of
    # FirstName/LastName/CompanyName. LastName is "Thomas" and is unique. Match on
    # LastName, never on the FullName the UI and the MCP connector show.
    "Thomas":                              ("Guelph",  "ON", "N1H 3A1"),
}
FORBIDDEN_NEW = ["Whitfield", "Sorenson"]


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


def read_individuals():
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "LastName": 1, "FirstName": 1,
                                                         "CompanyName": 1, "Type": 1, SEG: 1}},
                                    "Criteria": {"SearchQuery": {"Type": {"$EQ": "Individual"}}},
                                    "Options": {"Limit": 500}}, "Compatibility": COMPAT})
    rows = res.get("AbEntry", {}).get("Data") or []
    if not rows:
        sys.exit("0 Individuals returned. Refusing to act.")
    return rows


def contacts_of(parent):
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "FirstName": 1, "LastName": 1}},
                                    "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": parent}}},
                                    "Options": {"Limit": 100}}, "Compatibility": COMPAT})
    return res.get("AbEntry", {}).get("Data") or []


def address_of(parent):
    res = call("Read", {"Address": {"Scope": {"Fields": {"Key": 1, "City": 1, "StateProvince": 1,
                                                         "ZipCode": 1, "Country": 1, "Default": 1}},
                                    "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": parent}}},
                                    "Options": {"Limit": 20}}})
    return res.get("Address", {}).get("Data") or []


def main():
    apply = "--apply" in sys.argv
    if not PAT:
        sys.exit("No token. set -a; source futureproof.env; set +a")

    if "James and Margaret Dutton Family" not in FINGERPRINTS["futureproof"]["must_have"]:
        sys.exit("STOP: tenant_guard.py still fingerprints on 'Michael and Jennifer Cameron\n"
                 "Family', which this run renames. Repoint must_have at 'James and Margaret\n"
                 "Dutton Family' first, then re-run.")

    assert_tenant("futureproof", call)
    rows = read_individuals()
    by_name = {}
    for r in rows:
        by_name.setdefault(str(r.get("LastName") or ""), []).append(r)

    problems = []
    for n in list(RENAMES) + PROMOTE_TO_A + list(ADDRESSES):
        hits = by_name.get(n, [])
        if len(hits) != 1:
            problems.append("%r matches %d records, expected 1" % (n, len(hits)))
    for n in FORBIDDEN_NEW:
        clash = [k for k in by_name if n in k]
        if clash:
            problems.append("new surname %r already in use: %s" % (n, clash))
    if problems:
        sys.exit("SELECTION PROBLEMS - nothing written:\n  " + "\n  ".join(problems))
    print("  %d Individuals. All %d targets resolve to exactly one record."
          % (len(rows), len(RENAMES) + len(PROMOTE_TO_A) + len(ADDRESSES)))

    plan = []
    for old, new in RENAMES.items():
        hh = by_name[old][0]
        cs = contacts_of(hh["Key"])
        plan.append(("rename", hh, new, cs))
        print("  rename  %-38s -> %-38s (%d contacts)" % (old, new, len(cs)))
    for n in PROMOTE_TO_A:
        hh = by_name[n][0]
        print("  segment %-38s %s -> 1" % (n, one(hh.get(SEG))))
        plan.append(("segment", hh, "1", None))
    for n, (city, prov, zc) in ADDRESSES.items():
        hh = by_name[n][0]
        addrs = address_of(hh["Key"])
        cur = ", ".join("%s/%s" % (a.get("City"), a.get("StateProvince")) for a in addrs) or "none"
        print("  address %-38s [%s] -> %s/%s  (%d address rows)" % (n, cur, city, prov, len(addrs)))
        plan.append(("address", hh, (city, prov, zc), addrs))

    lou = [c for c in contacts_of(by_name["Cameron Family"][0]["Key"])
           if str(c.get("FirstName")) == "Lou"]
    print("  children field on Lou: %s" % ("found" if lou else "LOU NOT FOUND"))

    if not apply:
        print("\nDRY RUN. Re-run with --apply to write.")
        return

    print("\napplying...")
    for kind, hh, val, extra in plan:
        if kind == "rename":
            out = call("Update", {"AbEntry": {"Data": {"Key": hh["Key"], "LastName": val}},
                                  "Compatibility": COMPAT})
            print("  household %-38s code %s" % (val, out.get("Code")))
            sur = CONTACT_SURNAME[str(hh["LastName"])]
            for c in extra:
                o = call("Update", {"AbEntry": {"Data": {"Key": c["Key"], "LastName": sur}},
                                    "Compatibility": COMPAT})
                print("    contact %-20s -> %-12s code %s" % (c.get("FirstName"), sur, o.get("Code")))
        elif kind == "segment":
            out = call("Update", {"AbEntry": {"Data": {"Key": hh["Key"], SEG: val}},
                                  "Compatibility": COMPAT})
            print("  segment  %-38s code %s" % (hh.get("LastName"), out.get("Code")))
        elif kind == "address":
            city, prov, zc = val
            for a in extra:
                o = call("Update", {"AbEntry": {"Data": {
                    "Key": hh["Key"],
                    "Address": {"Key": a["Key"], "City": city, "StateProvince": prov,
                                "ZipCode": zc, "Country": "Canada"}}},
                    "Compatibility": COMPAT})
                print("  address  %-38s %s/%s code %s" % (hh.get("LastName"), city, prov, o.get("Code")))

    if lou:
        o = call("Update", {"AbEntry": {"Data": {"Key": lou[0]["Key"],
                                                 CHILDREN: "Paula and Roberto"}},
                            "Compatibility": COMPAT})
        print("  children on Lou code %s" % o.get("Code"))

    m = json.load(open(MANIFEST))
    m["part2"] = {"renamed": {o: n for o, n in RENAMES.items()},
                  "promoted_to_A": PROMOTE_TO_A,
                  "addresses_changed": list(ADDRESSES)}
    json.dump(m, open(MANIFEST, "w"), indent=1)

    print("\nreading back...")
    after = read_individuals()
    names = [str(r.get("LastName")) for r in after]
    print("  households: %d" % len(after))
    print("  named Cameron: %s" % [n for n in names if "Cameron" in n])
    print("  Segmentation 1: %s" % sorted(str(r.get("LastName")) for r in after
                                          if str(one(r.get(SEG))) == "1"))
    for n in ADDRESSES:
        hh = [r for r in after if str(r.get("LastName")) == n]
        if hh:
            a = address_of(hh[0]["Key"])
            print("  %-38s %s" % (n, ", ".join("%s/%s" % (x.get("City"), x.get("StateProvince")) for x in a)))
    for old, new in RENAMES.items():
        if new not in names:
            print("  !! %s did not store" % new)


if __name__ == "__main__":
    main()
