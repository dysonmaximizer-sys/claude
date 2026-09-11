#!/usr/bin/env python3
"""Give the top-AUM Futureproof households a call history.

WHY: "what share of my book is in my top ten households, and when did I last
speak to each" surfaced households with no contact record. Ten of the top
twelve by AUM hold zero InteractionLog rows. Every one of them HAS a Date Last
Contacted value, so the missing dates in that answer were a field-discovery
problem, not a data gap -- but the missing CALLS are real.

WHY NOT ALL 75: InteractionLog is the connector's readable timeline object and
it caps at 100 rows with no paging. 52 rows now; two calls each for ten
households lands at 72. Seeding the whole book would push it past 100 and make
EVERY call invisible on stage, breaking the thing this is meant to fix.

The most recent call for each household is dated EXACTLY on its Date Last
Contacted, so the two never disagree in front of an audience. Back-dated
interactions do not move that field (CLAUDE.md), and the script checks.

  set -a; source futureproof.env; set +a
  python3 engine/seed-top-households-history.py            # dry run
  python3 engine/seed-top-households-history.py --apply
"""
import argparse, base64, json, os, sys, time
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
TODAY = datetime.now(PACIFIC).date()

MANIFEST = "manifests/futureproof/top-households-history.json"
INTERACTION_CAP = 100          # connector cannot page past this
MASTER = "VXNlcglNQVNURVI="
PHONE, OUT, INB = "60001", 2, 1

DLC = "Udf/$TYPEID(60059)"
NEXT_KYC = "Udf/$TAG(WME_CLIENTINFO_REV_NEXTKYC)"
AUDIT_MARKERS = ["changed from", "field changed", "modified", "changed to",
                 "hotlist task", "opportunity created", "date last contacted"]

# Top-AUM households with no call history (verified 2026-09-11). Cameron and
# Hartfield are excluded: they already carry their own stories.
TARGETS = [
    "Charbonneau Household",
    "Gilles and Renee Desrosiers Family",
    "Pierre-Luc and Sylvie Boissonneault Family",
    "Desmond and Colette Lindqvist Family",
    "Milena and Dmitri Ferreira Family",
    "Takeshi and Hiroko Ishikawa Family",
    "Dallaire Household",
    "Jun and Mei Yamashita Family",
    "Mei and Kenji Nakamura Family",
    "Graham",
]

# Rotated so ten households do not read as one template. {who} {n} {kyc} {city}
RECENT = [
    ("Annual review call",
     "Annual review with {who}. Walked through all {n} accounts and the current allocation. "
     "No changes requested. Next KYC review booked for {kyc}."),
    ("Portfolio review call",
     "Reviewed the portfolio with {who}. Confirmed the contribution plan for the year and "
     "left the allocation as it stands. KYC review due {kyc}."),
    ("Semi-annual check-in",
     "Semi-annual check-in with {who}. Went through performance across the {n} accounts; "
     "no action arising. Confirmed the {kyc} KYC date."),
    ("Mid-year review call",
     "Mid-year review with {who} in {city}. Covered allocation and contribution room. "
     "Nothing outstanding. Next KYC review {kyc}."),
    ("Account review call",
     "Reviewed the {n} accounts with {who}. Statements and beneficiary details confirmed "
     "as current. KYC review scheduled for {kyc}."),
]
EARLIER = [
    (INB, "Statement question",
     "{who} called with a question about how to read the market value column on the "
     "statement. Walked through it; no follow-up needed."),
    (OUT, "Contribution reminder call",
     "Called {who} ahead of the contribution deadline to confirm the plan for the year. "
     "Confirmed, no change."),
    (INB, "Address and banking update",
     "{who} called to update mailing details on file. Updated the record the same day."),
    (OUT, "Portfolio check-in",
     "Short proactive call to {who} during a market pullback. No action taken; happy to "
     "stay the course."),
    (INB, "Tax slip request",
     "{who} asked for duplicate tax slips for their accountant. Sent from the record."),
]


def call(endpoint: str, payload: dict) -> dict:
    for attempt in range(6):
        r = requests.post("%s/%s" % (BASE, endpoint),
                          headers={"Authorization": "Bearer %s" % PAT,
                                   "Content-Type": "application/json"},
                          json=payload, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 0)) or 10 * (attempt + 1)); continue
        if r.status_code in (401, 403):
            sys.exit("AUTH FAILED (%s). Check futureproof.env." % r.status_code)
        r.raise_for_status(); time.sleep(0.35); return r.json()
    raise RuntimeError("rate-limited on %s" % endpoint)


def one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def rid(k: str) -> str:
    try:
        parts = base64.b64decode(k).decode("latin-1").split("\t")
    except Exception:
        return k
    return "\t".join(parts[1:]) if len(parts) > 1 else k


def dt(day, hm: str) -> str:
    local = datetime(day.year, day.month, day.day, int(hm[:2]), int(hm[3:5]), tzinfo=PACIFIC)
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def created_key(data: dict, obj: str) -> Optional[str]:
    node = (data.get(obj) or {}).get("Data")
    if isinstance(node, list) and node:
        return node[0].get("Key")
    return node.get("Key") if isinstance(node, dict) else None


def names_for(hh_key: str, contacts: list) -> str:
    firsts = [str(c.get("FirstName") or "").strip()
              for c in contacts if rid(c.get("ParentKey") or "") == rid(hh_key)]
    firsts = [f for f in firsts if f]
    if not firsts:
        return "the client"
    if len(firsts) == 1:
        return firsts[0]
    return "%s and %s" % (", ".join(firsts[:-1]), firsts[-1])


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    apply = ap.parse_args().apply
    if not PAT:
        sys.exit("No token. Run: set -a; source futureproof.env; set +a")

    print("== Top-household call history ==  run date %s" % TODAY)
    assert_tenant("futureproof", call)

    rows = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "LastName": 1, DLC: 1,
                                                          NEXT_KYC: 1, "Address/City": 1}},
                                     "Criteria": {"SearchQuery": {"Type": {"$EQ": "Individual"}}},
                                     "Options": {"Limit": 500}}, "Compatibility": COMPAT}) \
        .get("AbEntry", {}).get("Data") or []
    if not rows:
        sys.exit("0 Individuals returned: broken read, not an empty book. Nothing written.")
    contacts = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "FirstName": 1, "ParentKey": 1}},
                                         "Criteria": {"SearchQuery": {"Type": {"$EQ": "Contact"}}},
                                         "Options": {"Limit": 500}}, "Compatibility": COMPAT}) \
        .get("AbEntry", {}).get("Data") or []
    existing = call("Read", {"InteractionLog": {"Scope": {"Fields": {"Key": 1}},
                                                "Options": {"Limit": 200}}, "Compatibility": COMPAT}) \
        .get("InteractionLog", {}).get("Data") or []

    plan = []
    for i, nm in enumerate(TARGETS):
        m = [r for r in rows if " ".join(str(r.get("LastName") or "").split()) == nm]
        if len(m) != 1:
            sys.exit("Expected exactly one %r, found %d. Nothing written." % (nm, len(m)))
        r = m[0]
        dlc = one(r.get(DLC))
        if not dlc:
            sys.exit("%r has no Date Last Contacted. Run the coverage-decay fix first." % nm)
        last = datetime.strptime(str(dlc)[:10], "%Y-%m-%d").date()
        ctx = {"who": names_for(r["Key"], contacts),
               "n": "three", "kyc": str(one(r.get(NEXT_KYC)) or "the next review")[:10],
               "city": str(r.get("Address/City") or "")}
        rsub, rdesc = RECENT[i % len(RECENT)]
        edir, esub, edesc = EARLIER[i % len(EARLIER)]
        plan.append({
            "name": nm, "key": r["Key"], "last": last,
            "recent": (last, OUT, 25 + (i % 5) * 3, rsub, rdesc.format(**ctx)),
            "earlier": (last - timedelta(days=155 + i * 11), edir, 8 + (i % 4) * 3,
                        esub, edesc.format(**ctx)),
        })

    projected = len(existing) + 2 * len(plan)
    print("  interactions now %d, projected %d (connector cap %d)" % (len(existing), projected, INTERACTION_CAP))
    if projected > INTERACTION_CAP:
        sys.exit("REFUSING: %d would exceed the connector's %d-row cap and make ALL calls "
                 "invisible on stage. Trim TARGETS." % (projected, INTERACTION_CAP))

    print("\n  planned:")
    for p in plan:
        print("    %-42s %s  %s" % (p["name"][:41], p["earlier"][0], p["earlier"][3]))
        print("    %-42s %s  %s  <- matches Date Last Contacted" % ("", p["recent"][0], p["recent"][3]))

    if not apply:
        print("\nDRY RUN. Re-run with --apply to write."); return
    if os.path.exists(MANIFEST):
        print("\n%s exists - calls already seeded. Nothing to do." % MANIFEST); return

    before = {p["key"]: one([r for r in rows if r["Key"] == p["key"]][0].get(DLC)) for p in plan}
    manifest = {"story": "top-households-history", "tenant": "futureproof",
                "created": [], "seeded": TODAY.isoformat()}
    print("\ncreating calls...")
    for p in plan:
        for slot in ("earlier", "recent"):
            day, direction, mins, subj, desc = p[slot]
            data = call("Create", {"InteractionLog": {"Data": {
                "Key": None, "Subject": subj, "Description": desc, "Type": PHONE,
                "StartDate": dt(day, "10:00"), "EndDate": dt(day, "10:%02d" % mins),
                "User": MASTER, "AbEntryKey": p["key"], "Direction": direction}},
                "Compatibility": COMPAT})
            k = created_key(data, "InteractionLog")
            print("  %-42s %s %-26s %s" % (p["name"][:41], day, subj,
                                           "ok" if k else "FAILED " + json.dumps(data)[:180]))
            if k:
                manifest["created"].append({"kind": "InteractionLog", "key": k,
                                            "label": "%s - %s" % (p["name"], subj)})
        with open(MANIFEST, "w") as fh:
            json.dump(manifest, fh, indent=2)
    print("  manifest: %s (%d records)" % (MANIFEST, len(manifest["created"])))

    print("\nsweeping audit notes (last 10 minutes)...")
    cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=10)
    swept = kept = 0
    for p in plan:
        res = call("Read", {"Note": {"Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
                                     "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": p["key"]}}},
                                     "Options": {"Limit": 200}}, "Compatibility": COMPAT})
        for note in res.get("Note", {}).get("Data") or []:
            try:
                when = datetime.strptime(str(note.get("DateTime") or "")[:19],
                                         "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
            except ValueError:
                continue
            if when < cutoff:
                continue
            if any(m in str(note.get("Text") or "").lower() for m in AUDIT_MARKERS):
                if call("Delete", {"Note": {"Data": {"Key": note["Key"]}},
                                   "Compatibility": COMPAT}).get("Code", 0) == 0:
                    swept += 1
            else:
                kept += 1
    print("  %d swept, %d kept" % (swept, kept))

    print("\nverifying...")
    rows2 = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "LastName": 1, DLC: 1}},
                                      "Criteria": {"SearchQuery": {"Type": {"$EQ": "Individual"}}},
                                      "Options": {"Limit": 500}}, "Compatibility": COMPAT})["AbEntry"]["Data"]
    il2 = call("Read", {"InteractionLog": {"Scope": {"Fields": {"Key": 1, "AbEntryKey": 1, "StartDate": 1}},
                                           "Options": {"Limit": 200}}, "Compatibility": COMPAT}) \
        .get("InteractionLog", {}).get("Data") or []
    counts = {}
    for x in il2:
        counts[rid(x.get("AbEntryKey"))] = counts.get(rid(x.get("AbEntryKey")), 0) + 1
    drift = []
    for p in plan:
        now = one([r for r in rows2 if r["Key"] == p["key"]][0].get(DLC))
        n = counts.get(rid(p["key"]), 0)
        flag = "" if str(now) == str(before[p["key"]]) else "  !! DLC MOVED %s -> %s" % (before[p["key"]], now)
        if flag:
            drift.append(p["name"])
        print("  %-42s calls=%d  lastContacted=%s%s" % (p["name"][:41], n, now, flag))
    print("\n  interactions in tenant: %d / %d cap" % (len(il2), INTERACTION_CAP))
    if drift:
        print("  !! Date Last Contacted moved on %d household(s). Re-run:" % len(drift))
        print("     python3 engine/fix-futureproof-coverage-decay.py --apply")


if __name__ == "__main__":
    main()
