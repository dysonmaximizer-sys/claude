#!/usr/bin/env python3
"""
Test D: Full opportunity lifecycle via the Octopus API — create, update,
re-update, count. This is the test that decides whether the Demo Engine's
refresh loop is deterministic.

What it does (against the DEMO tenant only):
  1. Finds a cast contact (default: Jameson Thomas) and prints what it found,
     so you can confirm it grabbed the real cast record.
  2. Asks Maximizer which fields ARE mandatory for opportunity creation in
     your tenant (Validate call) and prints them.
  3. Lists your tenant's sales processes and status options.
  4. Creates ONE opportunity on that contact by KEY (no name matching).
  5. Updates it (revenue 250k -> 275k), then updates it AGAIN —
     simulating two refresh cycles.
  6. Counts opportunities on the contact. Success = exactly 1.
  7. Prints the cleanup command. Nothing is deleted automatically, so you
     can inspect the record in the UI first.

Setup (same as Test C):
  export MAXIMIZER_PAT="<PAT for the DEMO tenant>"
  export MAXIMIZER_BASE_URL="https://api.maximizer.com/octopus"   # if regional
  pip install requests

Run:
  python3 test-d-opportunity-lifecycle.py
  python3 test-d-opportunity-lifecycle.py --contact "Lou" "Cameron"
  python3 test-d-opportunity-lifecycle.py --cleanup "<opportunity key>"

Payload shapes follow Maximizer's Octopus API Opportunity docs (July 2026).
Your tenant's business rules may demand extra mandatory fields (e.g. Leader,
SalesTeam, CloseDate) — step 2 surfaces that BEFORE we attempt the create.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("pip install requests --break-system-packages")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")

OBJECTIVE = "TEST-KIT Test D - Retirement Income Transition"


def call(endpoint: str, payload: dict, quiet: bool = False) -> dict:
    r = requests.post(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("Code", 0) != 0 and not quiet:
        print(f"  !! API Code={data.get('Code')} on {endpoint}:")
        print(json.dumps(data, indent=2)[:1500])
    return data


def find_contact_key(first: str, last: str) -> str:
    data = call("Read", {
        "AbEntry": {
            "Scope": {"Fields": {"Key": 1, "FirstName": 1, "LastName": 1, "Type": 1, "CompanyName": 1}},
            "Criteria": {
                "SearchQuery": {"$AND": [
                    {"FirstName": {"$EQ": first}},
                    {"LastName": {"$EQ": last}},
                ]},
                "Top": 5,
            },
        },
        "Compatibility": {"AbEntryKey": "2.0"},
    })
    entries = data.get("AbEntry", {}).get("Data", [])
    if not entries:
        sys.exit(f"No AbEntry found for {first} {last}. Wrong tenant?")
    for e in entries:
        print(f"  found: {e.get('FirstName')} {e.get('LastName')} | type={e.get('Type')} | parent={e.get('CompanyName')} | key={e.get('Key')}")
    if len(entries) > 1:
        print("  ** More than one match (possibly leftovers from the wizard test).")
        print("  ** Using the first CONTACT-type entry. Verify above that it's the cast record.")
        for e in entries:
            if e.get("Type") == "Contact":
                return e["Key"]
    return entries[0]["Key"]


def show_mandatory_fields(abentry_key: str) -> None:
    data = call("Validate", {
        "Opportunity": {"Data": {"Key": None, "AbEntryKey": abentry_key}},
        "Configuration": {"Drivers": {"IOpportunityAccess": "Maximizer.Model.Access.Sql.OpportunityAccess"}},
    }, quiet=True)
    validation = data.get("Opportunity", {}).get("Validation", {})
    if validation:
        mandatory = [f for f, v in validation.items() if isinstance(v, dict) and v.get("Mandatory")]
        print(f"  tenant says mandatory for create: {', '.join(mandatory) or '(none beyond basics)'}")
    else:
        print("  (Validate endpoint returned nothing usable - continuing; the create attempt will tell us.)")


def show_field_options() -> None:
    data = call("Read", {
        "Opportunity": {"FieldOptions": {
            "SalesProcessSetup": [{"Key": 1, "DisplayValue": 1}],
            "Status": [{"Key": 1, "DisplayValue": 1}],
        }},
        "Compatibility": {"SchemaObject": "1.0"},
    }, quiet=True)
    opts = data.get("Opportunity", {}).get("FieldOptions", {})
    for name in ("SalesProcessSetup", "Status"):
        vals = opts.get(name) or []
        pretty = ", ".join(str(v.get("DisplayValue")) for v in vals[:8])
        print(f"  {name}: {pretty or '(none returned)'}")


def create_opportunity(abentry_key: str) -> Optional[str]:
    close = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    payload = {
        "Opportunity": {"Data": {
            "Key": None,
            "AbEntryKey": abentry_key,          # mandatory - the KEY, not a name
            "Objective": OBJECTIVE,             # mandatory
            "Description": "TEST-KIT: created via API to validate deterministic refresh.",
            "Status": 2,                        # In Progress (check Status options above if this errors)
            "ForecastRevenue": 250000,
            "CloseDate": f"{close}T12:00:00Z",
        }},
        "Compatibility": {"AbEntryKey": "2.0"},
    }
    data = call("Create", payload)
    key = data.get("Opportunity", {}).get("Data", {}).get("Key")
    if key:
        print(f"  created: revenue=250000, close={close}, key={key}")
    else:
        print("  create FAILED - if the error above names mandatory fields (Leader, SalesTeam,")
        print("  SalesStageSetupKey...), tell Claude which ones and the script gets extended.")
    return key


def update_opportunity(opp_key: str, revenue: int, cycle: int) -> None:
    close = (datetime.now() + timedelta(days=30 + 7 * cycle)).strftime("%Y-%m-%d")
    data = call("Update", {
        "Opportunity": {"Data": {
            "Key": opp_key,
            "ForecastRevenue": revenue,
            "CloseDate": f"{close}T12:00:00Z",
            "Description": f"TEST-KIT: refresh cycle {cycle} applied via API.",
        }},
    })
    if data.get("Code", 0) == 0:
        print(f"  refresh cycle {cycle}: revenue -> {revenue}, close -> {close}")


def count_and_show(abentry_key: str) -> None:
    # An opportunity created on a Contact stores the parent in AbEntryKey and
    # the contact in ContactKey - search both (per Maximizer's docs example).
    data = call("Read", {
        "Opportunity": {
            "Scope": {"Fields": {"Key": 1, "Objective": 1, "ForecastRevenue": 1, "Description": 1}},
            "Criteria": {
                "SearchQuery": {"$OR": [
                    {"AbEntryKey": {"$EQ": abentry_key}},
                    {"ContactKey": {"$EQ": abentry_key}},
                ]},
                "Top": 20,
            },
        },
        "Compatibility": {"AbEntryKey": "2.0"},
        "Configuration": {"Drivers": {"IOpportunitySearcher": "Maximizer.Model.Access.Sql.OpportunitySearcher"}},
    })
    opps = data.get("Opportunity", {}).get("Data", [])
    test_opps = [o for o in opps if OBJECTIVE in str(o.get("Objective", ""))]
    print(f"  opportunities on this contact: {len(opps)} total, {len(test_opps)} from this test")
    for o in test_opps:
        print(f"    stored: revenue={o.get('ForecastRevenue')} | {o.get('Description')} | key={o.get('Key')}")
    print()
    if len(test_opps) == 1:
        print("  VERDICT: exactly 1 test opportunity after 2 refresh cycles -> deterministic refresh WORKS.")
    elif len(test_opps) > 1:
        print("  VERDICT: duplicates appeared even via API - something is off, send Claude the output.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contact", nargs=2, metavar=("FIRST", "LAST"), default=["Jameson", "Thomas"])
    ap.add_argument("--cleanup", metavar="OPP_KEY")
    args = ap.parse_args()

    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only, never production).")

    if args.cleanup:
        call("Delete", {"Opportunity": {"Data": {"Key": args.cleanup}}})
        print("  deleted.")
        return

    first, last = args.contact
    print(f"1) Looking up {first} {last} ...")
    key = find_contact_key(first, last)

    print("2) Asking tenant which opportunity fields are mandatory ...")
    show_mandatory_fields(key)

    print("3) Tenant sales processes / status options ...")
    show_field_options()

    print("4) Creating opportunity by key ...")
    opp_key = create_opportunity(key)
    if not opp_key:
        sys.exit(1)

    print("5) Simulating two refresh cycles ...")
    update_opportunity(opp_key, 275000, cycle=1)
    update_opportunity(opp_key, 290000, cycle=2)

    print("6) Counting opportunities on the contact ...")
    count_and_show(key)

    print("Now check the UI: open the contact, confirm ONE opportunity with revenue 290,000,")
    print("and confirm NO new Address Book entries were created.")
    print(f'\nCleanup when done:\n  python3 test-d-opportunity-lifecycle.py --cleanup "{opp_key}"')


if __name__ == "__main__":
    main()
