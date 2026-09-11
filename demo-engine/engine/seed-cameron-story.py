#!/usr/bin/env python3
"""Seed the Cameron story onto the Futureproof hero household. Spec:
stories/futureproof/cameron-story.md. Read that first.

Carries the story in InteractionLog Descriptions and open Tasks ONLY, because
those are the two timeline objects the MCP connector can read in full on
stage. Notes and Appointments exceed the connector's 100-row cap and cannot be
filtered or paged, so anything written there may never be seen.

Idempotent. Calls and tasks are created once, guarded by the manifest. The
existing 2026-05-30 decay call gets its Description enriched (not duplicated).
Household fields are set on every run. Dates are relative to the run date.

  set -a; source futureproof.env; set +a
  python3 engine/seed-cameron-story.py            # dry run
  python3 engine/seed-cameron-story.py --apply
"""
import argparse, json, os, sys, time
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

MANIFEST = "manifests/futureproof/cameron-story.json"
DECAY_MANIFEST = "manifests/futureproof/coverage-decay.json"
HOUSEHOLD = "Peter and Mary Cameron Family"
MASTER = "VXNlcglNQVNURVI="
PHONE = "60001"
OUT, IN = 2, 1

DLC = "Udf/$TYPEID(60059)"
WILL_SIGNED = "Udf/$TYPEID(952)"        # Yes=2 No=1
WILL_UPDATED = "Udf/$TYPEID(953)"       # date
EXECUTOR_NAMED = "Udf/$TYPEID(970)"     # Yes=2 No=1
BENEF_REGISTERED = "Udf/$TYPEID(956)"   # Yes=2 No=1
LAST_ESTATE_REVIEW = "Udf/$TYPEID(841)"
NEXT_KYC = "Udf/$TAG(WME_CLIENTINFO_REV_NEXTKYC)"
YES, NO = "2", "1"

AUDIT_MARKERS = ["changed from", "field changed", "modified", "changed to",
                 "hotlist task", "opportunity created", "date last contacted"]

# (days back, direction, minutes, subject, description)
CALLS = [
    (700, OUT, 35, "Annual review call",
     "Annual review with Peter and Mary. Confirmed 2025 RRIF minimum withdrawals on both "
     "accounts. Mary asked whether the statements can be simplified. Peter raised the idea "
     "of selling the Penticton rental property this year; no decision yet."),
    (540, IN, 12, "Mary - rental property sold",
     "Mary called: the Penticton rental has sold, closing in May, roughly $300K coming into "
     "the joint account. Asked what they should do with it. Agreed to hold it in the joint "
     "cash account for now and review at the next meeting."),
    (450, OUT, 20, "Follow-up on sale proceeds",
     "Followed up on the rental proceeds now sitting in the joint account. Peter wants it "
     "kept liquid and does not want market exposure at his age. Agreed to revisit in the "
     "fall. Also raised that their will has not been reviewed since 2015; they will think "
     "about it."),
    (300, IN, 15, "Peter - RRIF withdrawal timing",
     "Peter called about timing the December RRIF withdrawal for tax. Confirmed the plan. "
     "He mentioned his brother, who is named as their executor, had a health scare over the "
     "summer and is now 86."),
    (180, OUT, 18, "Spring check-in",
     "Spring check-in with both. Mary asked who is currently listed as beneficiary on the "
     "registered accounts and could not recall. I said I would confirm the designations "
     "with Investia and come back to them. Cash in the joint account still uninvested."),
]
DECAY_CALL_DESCRIPTION = (
    "Reviewed the three registered accounts and the joint cash account, which still holds "
    "about $312K uninvested from the property sale. Peter remains reluctant to invest it. "
    "Agreed to book a fall review and bring their daughter into the conversation about the "
    "estate plan and who should act as executor going forward.")

# (days back, priority, activity)
TASKS = [
    (180, "Hi", "Confirm beneficiary designations on Peter and Mary's registered accounts with Investia"),
    (95, "Hi", "Book fall review with Peter and Mary; invite their daughter to discuss estate plan and executor"),
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


def dt(days_ago: int, hm: str) -> str:
    day = TODAY - timedelta(days=days_ago)
    local = datetime(day.year, day.month, day.day, int(hm[:2]), int(hm[3:5]), tzinfo=PACIFIC)
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def created_key(data: dict, obj: str) -> Optional[str]:
    node = (data.get(obj) or {}).get("Data")
    if isinstance(node, list) and node:
        return node[0].get("Key")
    return node.get("Key") if isinstance(node, dict) else None


def resolve_household() -> str:
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "LastName": 1}},
                                    "Criteria": {"SearchQuery": {"Type": {"$EQ": "Individual"}}},
                                    "Options": {"Limit": 500}}, "Compatibility": COMPAT})
    rows = res.get("AbEntry", {}).get("Data") or []
    if not rows:
        sys.exit("0 Individuals returned: broken read, not an empty book. Nothing written.")
    hits = [r for r in rows if " ".join(str(r.get("LastName") or "").split()) == HOUSEHOLD]
    if len(hits) != 1:
        sys.exit("Expected exactly one %r, found %d. Nothing written." % (HOUSEHOLD, len(hits)))
    return hits[0]["Key"]


def decay_call_key() -> Optional[str]:
    if not os.path.exists(DECAY_MANIFEST):
        return None
    for c in json.load(open(DECAY_MANIFEST)).get("created", []):
        if c.get("kind") == "InteractionLog" and HOUSEHOLD in c.get("label", ""):
            return c["key"]
    return None


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    apply = ap.parse_args().apply
    if not PAT:
        sys.exit("No token. Run: set -a; source futureproof.env; set +a")

    print("== Cameron story ==  run date %s" % TODAY)
    assert_tenant("futureproof", call)
    hh = resolve_household()
    decay_key = decay_call_key()
    manifest_exists = os.path.exists(MANIFEST)
    print("  household key      %s" % hh)
    print("  decay call to enrich: %s" % (decay_key or "NOT FOUND (will skip)"))
    print("  calls/tasks:       %s" % ("SKIP, manifest exists" if manifest_exists else "CREATE"))

    fields = {
        WILL_SIGNED: YES,
        WILL_UPDATED: (TODAY - timedelta(days=4108)).isoformat(),
        EXECUTOR_NAMED: YES,
        BENEF_REGISTERED: NO,
        LAST_ESTATE_REVIEW: (TODAY - timedelta(days=1460)).isoformat(),
        NEXT_KYC: (TODAY - timedelta(days=42)).isoformat(),
    }
    print("\n  household fields to set:")
    for k, v in fields.items():
        print("    %-42s = %s" % (k, v))
    print("\n  calls to create:")
    for d, direction, mins, subj, _ in CALLS:
        print("    %s  %-4s %2dmin  %s" % ((TODAY - timedelta(days=d)).isoformat(),
                                          "out" if direction == OUT else "in", mins, subj))
    print("  tasks to create:")
    for d, pri, act in TASKS:
        print("    %s  [%s]  %s" % ((TODAY - timedelta(days=d)).isoformat(), pri, act[:70]))

    if not apply:
        print("\nDRY RUN. Re-run with --apply to write."); return

    dlc_before = one(call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, DLC: 1}},
                                              "Criteria": {"SearchQuery": {"Key": {"$EQ": hh}}}},
                                   "Compatibility": COMPAT})["AbEntry"]["Data"][0].get(DLC))

    print("\nsetting household fields...")
    out = call("Update", {"AbEntry": {"Data": dict({"Key": hh}, **fields)}, "Compatibility": COMPAT})
    print("  code %s" % out.get("Code"))

    manifest = json.load(open(MANIFEST)) if manifest_exists else \
        {"story": "cameron-story", "tenant": "futureproof", "created": [], "seeded": TODAY.isoformat()}

    if not manifest_exists:
        print("\ncreating calls...")
        for d, direction, mins, subj, desc in CALLS:
            data = call("Create", {"InteractionLog": {"Data": {
                "Key": None, "Subject": subj, "Description": desc, "Type": PHONE,
                "StartDate": dt(d, "10:00"), "EndDate": dt(d, "10:%02d" % mins),
                "User": MASTER, "AbEntryKey": hh, "Direction": direction}},
                "Compatibility": COMPAT})
            k = created_key(data, "InteractionLog")
            print("  %-38s %s" % (subj, "ok" if k else "FAILED " + json.dumps(data)[:200]))
            if k:
                manifest["created"].append({"kind": "InteractionLog", "key": k, "label": subj})
        print("\ncreating tasks...")
        for d, pri, act in TASKS:
            data = call("Create", {"Task": {"Data": {
                "Key": None, "Activity": act, "DateTime": dt(d, "09:00"),
                "AbEntryKey": hh, "AssignedTo": MASTER, "Priority": pri}},
                "Compatibility": COMPAT})
            k = created_key(data, "Task")
            print("  %-70s %s" % (act[:70], "ok" if k else "FAILED " + json.dumps(data)[:200]))
            if k:
                manifest["created"].append({"kind": "Task", "key": k, "label": act[:60]})
        with open(MANIFEST, "w") as fh:
            json.dump(manifest, fh, indent=2)
        print("  manifest written: %s" % MANIFEST)

    if decay_key:
        print("\nenriching the 2026-05-30 decay call description...")
        out = call("Update", {"InteractionLog": {"Data": {"Key": decay_key,
                                                          "Description": DECAY_CALL_DESCRIPTION}},
                              "Compatibility": COMPAT})
        print("  code %s" % out.get("Code"))

    print("\nsweeping audit notes (last 10 minutes)...")
    cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=10)
    swept = kept = 0
    res = call("Read", {"Note": {"Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
                                 "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": hh}}},
                                 "Options": {"Limit": 300}}, "Compatibility": COMPAT})
    for note in res.get("Note", {}).get("Data") or []:
        try:
            when = datetime.strptime(str(note.get("DateTime") or "")[:19],
                                     "%Y-%m-%dT%H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
        except ValueError:
            continue
        if when < cutoff:
            continue
        text = str(note.get("Text") or "")
        if any(m in text.lower() for m in AUDIT_MARKERS):
            if call("Delete", {"Note": {"Data": {"Key": note["Key"]}}, "Compatibility": COMPAT}).get("Code", 0) == 0:
                swept += 1
        else:
            kept += 1; print("  ! recent non-audit note kept: %r" % text[:70])
    print("  %d swept, %d kept" % (swept, kept))

    print("\nverifying...")
    hhr = call("Read", {"AbEntry": {"Scope": {"Fields": dict({"Key": 1, DLC: 1}, **{k: 1 for k in fields})},
                                    "Criteria": {"SearchQuery": {"Key": {"$EQ": hh}}}},
                        "Compatibility": COMPAT})["AbEntry"]["Data"][0]
    for k in fields:
        print("  %-42s = %s" % (k, one(hhr.get(k))))
    il = call("Read", {"InteractionLog": {"Scope": {"Fields": {"Key": 1, "Subject": 1, "StartDate": 1, "Description": 1}},
                                          "Criteria": {"SearchQuery": {"AbEntryKey": {"$EQ": hh}}},
                                          "Options": {"Limit": 50}}, "Compatibility": COMPAT})
    rows = sorted(il.get("InteractionLog", {}).get("Data") or [], key=lambda x: str(x.get("StartDate")))
    print("  %d calls on the household:" % len(rows))
    for r in rows:
        print("    %s  %-36s desc=%d chars" % (str(r.get("StartDate"))[:10], r.get("Subject"), len(str(r.get("Description") or ""))))
    tk = call("Read", {"Task": {"Scope": {"Fields": {"Key": 1, "Activity": 1, "DateTime": 1, "Completed": 1}},
                                "Criteria": {"SearchQuery": {"AbEntryKey": {"$EQ": hh}}},
                                "Options": {"Limit": 50}}, "Compatibility": COMPAT})
    trows = tk.get("Task", {}).get("Data") or []
    print("  %d tasks on the household (%d open)" % (len(trows), sum(1 for t in trows if not t.get("Completed"))))

    dlc_after = one(hhr.get(DLC))
    print("\n  Date Last Contacted: before=%s after=%s" % (dlc_before, dlc_after))
    if dlc_before != dlc_after:
        print("  !! DATE LAST CONTACTED MOVED. Task/call creation auto-set it. Re-run the decay fix:")
        print("     set -a; source futureproof.env; set +a && python3 engine/fix-futureproof-coverage-decay.py --apply")


if __name__ == "__main__":
    main()
