#!/usr/bin/env python3
"""
Sail Through Audits — story seeder (Demo Centre gated tour 2).

Builds the Renaud household and NINE YEARS of ordered, time-stamped history
via the Octopus API, matching stories/sail-through-audits.md:

  Cast:      Renaud Family household — Philippe (68, RRIF conversion on the
             horizon), Céline (65 this year, owns the insurance thread).
  History:   annual review appointment + advice note each year for 9 years,
             phone calls scattered between (more in recent years), KYC
             refresh notes at realistic intervals.
  Today:     open task "Compile CIRO audit file — Renaud household".

Tenant constraints honoured (CLAUDE.md):
  - Emails CANNOT be fabricated (types 60002-60004 blocked). The trail is
    calls + notes + appointments; real emails come from Outlook capture
    between demo mailboxes in the days before recording (manual step).
  - Documents: create shape UNVALIDATED. This seeder PROBES one document
    create first; if the tenant accepts it, story documents are created
    (and the probe doc deleted). Either way it prints the result — fold it
    into CLAUDE.md.
  - Dates relative, times Pacific->UTC via zoneinfo, keys to manifest,
    audit-note sweep at the end.

Run:    python3 seed-sail-through-audits.py
        python3 seed-sail-through-audits.py --cleanup
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests --break-system-packages")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifests",
                        "sail-through-audits-manifest.json")

TODAY = datetime.now()
PACE = 0.35  # seconds between calls (429 protection, validated)


def d(days_offset: int, hm: str = "10:00") -> str:
    """API datetime, days relative to today; hm is INTENDED Pacific wall time,
    converted to UTC (validated 2026-07-15; zoneinfo knows B.C.'s permanent
    DST from Nov 2026)."""
    from zoneinfo import ZoneInfo
    day = TODAY + timedelta(days=days_offset)
    hour, minute = int(hm[:2]), int(hm[3:5])
    local = day.replace(hour=hour, minute=minute, second=0, microsecond=0,
                        tzinfo=ZoneInfo("America/Vancouver"))
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def call(endpoint: str, payload: dict, quiet: bool = False) -> dict:
    time.sleep(PACE)
    r = requests.post(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if r.status_code == 429:
        wait = int(r.headers.get("Retry-After", "5"))
        print(f"  .. rate limited, waiting {wait}s")
        time.sleep(wait)
        return call(endpoint, payload, quiet)
    r.raise_for_status()
    data = r.json()
    if data.get("Code", 0) != 0 and not quiet:
        print(f"  !! Code={data.get('Code')} on {endpoint}: {json.dumps(data)[:500]}")
    return data


def created_key(data: dict, obj: str) -> Optional[str]:
    return data.get(obj, {}).get("Data", {}).get("Key")


def remember(manifest: dict, kind: str, key: Optional[str], label: str) -> None:
    if key:
        manifest.setdefault("records", []).append({"kind": kind, "key": key, "label": label})
        print(f"  + {kind}: {label}")
    else:
        print(f"  - FAILED {kind}: {label}")


def _save(manifest: dict) -> None:
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)


# ---------------------------------------------------------------- cast

def create_household(manifest: dict) -> Optional[str]:
    data = call("Create", {
        "AbEntry": {"Data": {
            "Key": None, "Type": "Household", "CompanyName": "Renaud Family",
            "Address": {"AddressLine1": "88 Glebe Ave", "City": "Ottawa",
                        "StateProvince": "ON", "Country": "Canada", "ZipCode": "K1S 2C3"},
            "Phone1": {"Number": "(555) 010-7730"},
        }},
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    key = created_key(data, "AbEntry")
    if key:
        remember(manifest, "AbEntry", key, "Renaud Family (Household)")
    else:
        print(f"  household create rejected: {json.dumps(data)[:300]}")
    return key


def create_contact(manifest: dict, parent_key: str, first: str, last: str,
                   birthdate: str, email: str, phone: str) -> Optional[str]:
    data = call("Create", {
        "AbEntry": {"Data": {
            "Key": None, "Type": "Contact", "ParentKey": parent_key,
            "FirstName": first, "LastName": last,
            "Email": {"Address": email}, "Phone1": {"Number": phone},
            "Udf/$TYPEID(124)": birthdate,  # Birthdate UDF, validated
        }},
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    key = created_key(data, "AbEntry")
    if not key:  # retry without birthdate rather than fail the story
        data = call("Create", {
            "AbEntry": {"Data": {
                "Key": None, "Type": "Contact", "ParentKey": parent_key,
                "FirstName": first, "LastName": last,
                "Email": {"Address": email}, "Phone1": {"Number": phone},
            }},
            "Compatibility": {"AbEntryKey": "2.0"},
        }, quiet=True)
        key = created_key(data, "AbEntry")
        if key:
            print(f"    ({first}: created WITHOUT birthdate - set manually)")
    remember(manifest, "AbEntry", key, f"{first} {last}")
    return key


def set_profile(abentry_key: str, label: str) -> None:
    """Segmentation A, Next KYC Review +6 months, Date Last Contacted recent.
    All validated assignable UDFs. Generates audit notes -> swept later."""
    data = call("Update", {
        "AbEntry": {"Data": {
            "Key": abentry_key,
            "Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)": "1",
            "Udf/$TAG(WME_CLIENTINFO_REV_NEXTKYC)": (TODAY + timedelta(days=180)).strftime("%Y-%m-%d"),
            "Udf/$TYPEID(60059)": (TODAY - timedelta(days=9)).strftime("%Y-%m-%d"),
        }},
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    ok = data.get("Code", 0) == 0
    print(f"  {'+' if ok else '-'} profile set: {label}")


# ---------------------------------------------------------------- timeline

def interaction_type_key(display_contains: str) -> Optional[str]:
    data = call("Read", {
        "InteractionLog": {"FieldOptions": {"Type": [{"Key": 1, "DisplayValue": 1}]}},
        "Compatibility": {"SchemaObject": "1.0"},
    }, quiet=True)
    for opt in data.get("InteractionLog", {}).get("FieldOptions", {}).get("Type", []) or []:
        if display_contains.lower() in str(opt.get("DisplayValue", "")).lower():
            return str(opt.get("Key"))
    return None


def create_call_log(manifest: dict, abentry_key: str, type_key: str, subject: str,
                    description: str, days_ago: int, duration_min: int,
                    direction: int = 2) -> None:
    end_minute = duration_min % 60
    payload = {
        "Key": None, "Subject": subject, "Description": description,
        "Type": type_key,
        "StartDate": d(-days_ago, "10:00"),
        "EndDate": d(-days_ago, f"10:{end_minute:02d}"),
        "User": "$CURRENTUSER()", "AbEntryKey": abentry_key, "Direction": direction,
    }
    data = call("Create", {"InteractionLog": {"Data": payload},
                           "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "InteractionLog", created_key(data, "InteractionLog"), subject)


def create_note(manifest: dict, parent_key: str, text: str, days_ago: int,
                hm: str = "14:30") -> None:
    data = call("Create", {"Note": {"Data": {
        "Key": None, "ParentKey": parent_key,
        "DateTime": d(-days_ago, hm), "Text": text,
    }}})
    remember(manifest, "Note", created_key(data, "Note"), text[:48])


def create_appointment(manifest: dict, abentry_keys: list, subject: str,
                       description: str, days_ago: int) -> None:
    data = call("Create", {"Appointment": {"Data": {
        "Key": None, "Subject": subject,
        "StartDate": d(-days_ago, "10:00"), "EndDate": d(-days_ago, "11:00"),
        "Description": description, "AbEntries": abentry_keys,
    }}, "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "Appointment", created_key(data, "Appointment"), subject)


def create_task(manifest: dict, abentry_key: str, activity: str, due_in_days: int) -> None:
    data = call("Create", {"Task": {"Data": {
        "Key": None, "Activity": activity,
        "DateTime": d(due_in_days, "17:00"), "AbEntryKey": abentry_key,
    }}, "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "Task", created_key(data, "Task"), activity)


# ---------------------------------------------------------------- documents (PROBE)

def probe_documents(manifest: dict, abentry_key: str) -> bool:
    """Document create is UNVALIDATED on this tenant. Try one small create,
    read it back, and report. On success the probe doc is kept ONLY if it
    fits the story; otherwise deleted. Fold the printed result into
    CLAUDE.md either way."""
    doc_bytes = base64.b64encode(
        b"DEMO PROBE - safe to delete. Testing Document create shape.").decode()
    shapes = [
        {"Key": None, "AbEntryKey": abentry_key, "Name": "probe.txt",
         "Description": "API probe", "DocData": doc_bytes},
        {"Key": None, "ParentKey": abentry_key, "Name": "probe.txt",
         "Description": "API probe", "DocData": doc_bytes},
        {"Key": None, "AbEntryKey": abentry_key, "DocumentName": "probe.txt",
         "Description": "API probe", "Data64": doc_bytes},
    ]
    for i, shape in enumerate(shapes, 1):
        data = call("Create", {"Document": {"Data": shape},
                               "Compatibility": {"AbEntryKey": "2.0"}}, quiet=True)
        key = created_key(data, "Document")
        if key:
            print(f"  DOCUMENT PROBE: shape #{i} WORKED (fields: {sorted(shape.keys())}).")
            print("  >> Record in CLAUDE.md: Document create validated with this shape.")
            dele = call("Delete", {"Document": {"Data": {"Key": key}}}, quiet=True)
            print(f"  probe doc deleted: {dele.get('Code', '?') == 0}")
            return True
        print(f"  document shape #{i} rejected: {json.dumps(data)[:220]}")
    print("  DOCUMENT PROBE: all shapes rejected.")
    print("  >> Record in CLAUDE.md: Document create BLOCKED/unknown shape; "
          "story trail carries documents via notes instead.")
    return False


def create_document(manifest: dict, abentry_key: str, name: str, text: str,
                    days_ago: int) -> None:
    doc_bytes = base64.b64encode(text.encode()).decode()
    data = call("Create", {"Document": {"Data": {
        "Key": None, "AbEntryKey": abentry_key, "Name": name,
        "Description": name, "DocData": doc_bytes,
        "DateTime": d(-days_ago, "15:00"),
    }}, "Compatibility": {"AbEntryKey": "2.0"}}, quiet=True)
    remember(manifest, "Document", created_key(data, "Document"), name)


# ---------------------------------------------------------------- audit sweep

AUDIT_MARKERS = ("Hotlist Task Created", "Hotlist Task Modified", "Opportunity created",
                 "changed from", "Changed from")


def sweep_audit_notes(manifest: dict, parent_keys: list) -> None:
    """Delete tenant auto-logged audit notes stamped today on our parents.
    Notes have no CreationDate and DateTime rejects $GT: read all notes per
    parent, filter client-side (validated). Never touches keys we created."""
    ours = {r["key"] for r in manifest.get("records", []) if r["kind"] == "Note"}
    swept = 0
    for pk in parent_keys:
        if not pk:
            continue
        data = call("Read", {"Note": {
            "Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
            "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": pk}}},
        }}, quiet=True)
        for note in data.get("Note", {}).get("Data", []) or []:
            key, text = note.get("Key"), str(note.get("Text", ""))
            if key in ours:
                continue
            if any(m in text for m in AUDIT_MARKERS):
                dele = call("Delete", {"Note": {"Data": {"Key": key}}}, quiet=True)
                if dele.get("Code", 0) == 0:
                    swept += 1
    print(f"  swept {swept} audit note(s)")


# ---------------------------------------------------------------- verify

def verify(manifest: dict, hh: str) -> None:
    data = call("Read", {"Note": {
        "Scope": {"Fields": {"Key": 1, "DateTime": 1}},
        "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": hh}}},
    }}, quiet=True)
    notes = data.get("Note", {}).get("Data", []) or []
    print(f"  read-back: {len(notes)} notes on the household")
    dates = sorted(str(n.get("DateTime", "")) for n in notes if n.get("DateTime"))
    if dates:
        print(f"  oldest note: {dates[0][:10]}   newest: {dates[-1][:10]}")


# ---------------------------------------------------------------- main

def cleanup() -> None:
    if not os.path.exists(MANIFEST):
        sys.exit(f"No manifest at {MANIFEST} - nothing to clean.")
    with open(MANIFEST) as f:
        manifest = json.load(f)
    for rec in reversed(manifest.get("records", [])):
        data = call("Delete", {rec["kind"]: {"Data": {"Key": rec["key"]}}}, quiet=True)
        ok = data.get("Code", 0) == 0
        print(f"  {'deleted' if ok else 'FAILED to delete'} {rec['kind']}: {rec['label']}")
    os.remove(MANIFEST)
    print("Manifest removed.")


# Nine years of advisor-language history. days_ago ~ years*365 + jitter.
YEARLY = [
    (9, "Initial KYC and IPS signed. Risk profile: balanced. Consolidated two "
        "external accounts; set up PACs. Philippe retirement target age 70."),
    (8, "Annual review. Rebalanced to 60/40. Céline added as joint on "
        "non-registered account. Beneficiary designations confirmed."),
    (7, "Annual review. Topped up TFSAs both spouses. Discussed cottage "
        "purchase - parked pending price. KYC refreshed, no changes."),
    (6, "Annual review. Cottage purchased; adjusted cash reserve. Risk "
        "profile reconfirmed balanced. Céline insurance review flagged."),
    (5, "Annual review. Term-to-perm insurance conversion completed for "
        "Céline. Estate documents reviewed with lawyer - POAs updated."),
    (4, "Annual review. Philippe semi-retired; income plan drafted. Began "
        "RRSP meltdown discussion. KYC refreshed - income change recorded."),
    (3, "Annual review. Pension bridging elected. Rebalanced to 55/45. "
        "Discussed RRIF conversion timeline (Philippe turns 71 in 3 years)."),
    (2, "Annual review. Market volatility walkthrough - no changes, stayed "
        "the course. Céline government pension started; PAC reduced."),
    (1, "Annual review. RRIF conversion plan drafted for Philippe. Céline "
        "turning 65 - OAS application discussed. KYC refreshed, no changes."),
]

CALLS = [
    (9, 340, "Philippe - PAC setup confirmation", "Confirmed first PAC cleared; walked through statement access.", 9, 2),
    (8, 300, "Céline - joint account paperwork", "Signature pages missing page 3; resent via courier.", 12, 1),
    (7, 250, "Philippe - TFSA room question", "Confirmed contribution room from CRA MyAccount before top-up.", 8, 1),
    (6, 200, "Cottage closing - funds release", "Coordinated lawyer trust transfer for cottage closing.", 15, 2),
    (5, 170, "Céline - insurance conversion options", "Reviewed term-to-perm quotes; she chose 20-pay.", 22, 2),
    (4, 130, "Philippe - severance package review", "Walked through semi-retirement package; deferred bonus to Jan.", 25, 1),
    (3, 80, "Market check-in call", "Proactive call during pullback; no action, notes on file.", 14, 2),
    (2, 40, "Céline - pension start date", "Confirmed government pension start; PAC reduction from next month.", 10, 1),
    (1, 20, "RRIF timeline question (Philippe)", "Philippe asked whether to convert early; modelling at next review.", 16, 1),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup", action="store_true")
    args = ap.parse_args()

    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only). Load .env from the repo root.")

    if args.cleanup:
        cleanup()
        return

    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}). Run --cleanup first.")

    manifest = {"story": "sail-through-audits", "created": TODAY.isoformat()}

    print("1) Creating the Renaud household ...")
    hh = create_household(manifest)
    if not hh:
        _save(manifest)
        sys.exit("Household creation failed - paste this output back.")

    print("2) Creating Philippe (68) and Céline (65) ...")
    philippe = create_contact(manifest, hh, "Philippe", "Renaud",
                              (TODAY - timedelta(days=68 * 365 + 140)).strftime("%Y-%m-%d"),
                              "philippe.renaud@mail.test", "(555) 010-7731")
    celine = create_contact(manifest, hh, "Céline", "Renaud",
                            (TODAY - timedelta(days=65 * 365 + 40)).strftime("%Y-%m-%d"),
                            "celine.renaud@mail.test", "(555) 010-7732")
    if not philippe:
        _save(manifest)
        sys.exit("Primary contact failed - stopping.")

    print("3) Profiles (segmentation, KYC, last contacted) ...")
    for k, label in ((hh, "household"), (philippe, "Philippe"), (celine, "Céline")):
        if k:
            set_profile(k, label)

    print("4) Interaction type id ...")
    phone = interaction_type_key("phone")
    print(f"  phone type={phone}")

    print("5) Nine years of reviews and notes ...")
    for years_ago, text in YEARLY:
        days = years_ago * 365 + (years_ago * 11) % 28  # stable jitter, keeps order
        create_appointment(manifest, [k for k in (philippe, celine) if k] or [hh],
                           f"Renaud household annual review",
                           "Annual review meeting.", days)
        create_note(manifest, hh, text, days)

    print("6) Calls between reviews ...")
    if phone:
        for years_ago, extra_days, subject, desc, dur, direction in CALLS:
            create_call_log(manifest, hh, phone, subject, desc,
                            years_ago * 365 - extra_days, dur, direction)
    else:
        print("  !! phone type id not found - calls skipped, tell Claude")

    print("7) Document probe (unvalidated API) ...")
    docs_ok = probe_documents(manifest, hh)
    if docs_ok:
        create_document(manifest, hh, "Renaud IPS v3 (signed).txt",
                        "Investment Policy Statement v3 - balanced 55/45. Signed at annual review.", 380)
        create_document(manifest, hh, "KYC refresh confirmation.txt",
                        "KYC refresh - no material changes. Filed following annual review.", 372)

    print("8) The story-day task ...")
    create_task(manifest, hh, "Compile CIRO audit file - Renaud household (9 years)", 4)

    print("9) Sweeping audit notes ...")
    sweep_audit_notes(manifest, [hh, philippe, celine])

    print("10) Verifying with read-backs ...")
    verify(manifest, hh)

    _save(manifest)
    n = len(manifest.get("records", []))
    print(f"\nDone: {n} records created. Manifest: {MANIFEST}")
    print("\nEyeball checklist (Maximizer UI, Renaud Family household):")
    print("  - timeline spans ~9 years, oldest entries first, no gaps > 18 months")
    print("  - annual reviews show as past APPOINTMENTS with matching advice notes")
    print("  - phone calls show direction + duration and read like a real book")
    print("  - open task: 'Compile CIRO audit file' due this week")
    print("  - no same-day 'changed from X to Y' audit notes remain")
    print("\nManual before capture (engine cannot do this):")
    print("  - send 2-3 client-style emails between the demo mailboxes so real")
    print("    captured email shows in the recent window")
    print("  - compose Adam's CIRO forward in the demo Outlook mailbox")
    print("    (asset: Demo Centre/sail-through-audits-adam-email.md; never Resend)")
    print(f"\nRemove the whole story:  python3 seed-sail-through-audits.py --cleanup")


if __name__ == "__main__":
    main()
