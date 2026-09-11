#!/usr/bin/env python3
"""Refuse to run against the wrong Maximizer tenant.

WHY THIS EXISTS (validated 2026-09-09): CLAUDE.md says "record keys are
tenant-specific". That is FALSE for the FSE / Futureproof pair. Futureproof is
a clone of FSE taken after 2026-07-15: 22 Company records and 20 Individual
records share BYTE-IDENTICAL keys across the two books. A manifest built in one
resolves cleanly in the other, so a mis-sourced seeder, refresher or cleanup
edits real records and reports success. Nothing 404s. Nothing errors.

Key-based fingerprints cannot discriminate the two books. Names can: the books
diverged on the Cameron households. So the guard checks names, and it checks
both directions (a required record AND a forbidden one) so that a book which is
neither of the two fails rather than passing by accident.

Usage in a seeder, BEFORE the first write:

    from tenant_guard import assert_tenant
    assert_tenant("futureproof", call)
"""

import json
import sys
from typing import Callable, List

COMPAT = {"AbEntryKey": "2.0"}

# Individual-typed household names that exist in exactly one of the two books.
FINGERPRINTS = {
    "futureproof": {
        # "Michael and Jennifer Cameron Family" was renamed to Sorenson on 2026-09-09
        # (fix-futureproof-part2.py). Dutton replaces it: also Futureproof-only, and
        # not a rename target. Never fingerprint on a record a seeder renames.
        "must_have": ["Peter and Mary Cameron Family", "James and Margaret Dutton Family"],
        "must_not_have": ["Cameron"],
    },
    "fse": {
        "must_have": ["Cameron"],
        "must_not_have": ["Peter and Mary Cameron Family"],
    },
}


def _household_names(call: Callable) -> List[str]:
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "Type": 1, "LastName": 1}},
                                    "Criteria": {"SearchQuery": {"Type": {"$EQ": "Individual"}}},
                                    "Options": {"Limit": 500}}, "Compatibility": COMPAT})
    rows = res.get("AbEntry", {}).get("Data", [])
    if not rows:
        sys.exit("TENANT GUARD: the Individual read returned 0 rows. Refusing to write.\n"
                 "  An unknown field in Scope returns an empty set instead of an error in\n"
                 "  this API, so treat 0 rows as a broken probe, never as an empty book.")
    return [str(r.get("LastName") or "") for r in rows]


def assert_tenant(expected: str, call: Callable) -> None:
    if expected not in FINGERPRINTS:
        sys.exit("TENANT GUARD: no fingerprint defined for %r" % expected)
    fp = FINGERPRINTS[expected]
    names = _household_names(call)

    missing = [n for n in fp["must_have"] if n not in names]
    forbidden = [n for n in fp["must_not_have"] if n in names]

    if missing or forbidden:
        other = [t for t in FINGERPRINTS if t != expected]
        looks_like = [t for t in other
                      if all(n in names for n in FINGERPRINTS[t]["must_have"])
                      and not any(n in names for n in FINGERPRINTS[t]["must_not_have"])]
        sys.exit(
            "TENANT GUARD TRIPPED - NOTHING WAS WRITTEN.\n"
            "  expected tenant : %s\n"
            "  missing markers : %s\n"
            "  forbidden found : %s\n"
            "  this book looks like: %s\n"
            "  %d households read.\n"
            "  Fix: source the right env file in the SAME command as the run.\n"
            "       set -a; source futureproof.env; set +a" % (
                expected, json.dumps(missing), json.dumps(forbidden),
                looks_like[0] if looks_like else "NEITHER known book",
                len(names)))

    print("  tenant guard OK: confirmed %s (%d households)" % (expected, len(names)))
